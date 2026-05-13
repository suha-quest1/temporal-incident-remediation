import asyncio
import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker
from temporal.workflows import IncidentWorkflow
from temporal.sub_workflow import ExecuteStepWorkflow
from temporal.data.data_class import IncidentDetails, OverrideSignal
from temporalio import activity

# Mock constants
MOCK_CLASSIFY = {"incident_type": "OOM", "severity": "P1"}
MOCK_PLAN = ["kubectl rollout restart deployment/api"]
MOCK_PM_PATH = "/app/output/pm.md"

@activity.defn(name="ClassifyIncident")
async def mock_classify(msg): return MOCK_CLASSIFY

@activity.defn(name="FetchRunbook")
async def mock_fetch(tags): return "runbook content"

@activity.defn(name="GeneratePlan")
async def mock_plan(t, r, s): return MOCK_PLAN

@activity.defn(name="ExecuteStep")
async def mock_exec(cmd): return {"status": "success", "output": "ok"}

@activity.defn(name="RollbackChanges")
async def mock_rollback(cmds): return ["rollback: ok"]

@activity.defn(name="VerifyResolution")
async def mock_verify(svc): return {"healthy": True}

@activity.defn(name="GeneratePostmortem")
async def mock_pm(*args): return MOCK_PM_PATH

ALL_MOCKS = [mock_classify, mock_fetch, mock_plan, mock_exec, mock_rollback, mock_verify, mock_pm]
TASK_QUEUE = "test-queue"

def make_incident():
    return IncidentDetails(alertId="id", severity="P1", service="api", errorMessage="err", runbookTags=[])

async def test_full_orchestration_happy_path():
    """Validates the standard flow from classification to postmortem."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(env.client, task_queue=TASK_QUEUE, workflows=[IncidentWorkflow, ExecuteStepWorkflow], activities=ALL_MOCKS):
            result = await env.client.execute_workflow(IncidentWorkflow.run, make_incident(), id="wf-1", task_queue=TASK_QUEUE)
            assert result["postmortem_path"] == MOCK_PM_PATH
            assert result["rollback_result"] is None

async def test_rollback_signal_triggers_remediation_reversal():
    """Validates that a rollback signal actually triggers the rollback activity."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(env.client, task_queue=TASK_QUEUE, workflows=[IncidentWorkflow, ExecuteStepWorkflow], activities=ALL_MOCKS):
            handle = await env.client.start_workflow(IncidentWorkflow.run, make_incident(), id="wf-rollback", task_queue=TASK_QUEUE)
            await handle.signal(IncidentWorkflow.humanOverride, OverrideSignal(action="rollback", engineer="alice"))
            result = await handle.result()
            assert result["override_action"] == "rollback"
            assert result["rollback_result"] == ["rollback: ok"]

async def test_timer_expiry_proceeds_without_rollback():
    """Validates that the workflow finishes if no human signal arrives."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(env.client, task_queue=TASK_QUEUE, workflows=[IncidentWorkflow, ExecuteStepWorkflow], activities=ALL_MOCKS):
            result = await env.client.execute_workflow(IncidentWorkflow.run, make_incident(), id="wf-timer", task_queue=TASK_QUEUE)
            assert result["override_action"] is None
            assert result["rollback_result"] is None

async def test_transient_failure_retries_classification():
    """Ensures activity retry policy is respected for transient errors."""
    calls = 0
    @activity.defn(name="ClassifyIncident")
    async def flaky_classify(msg):
        nonlocal calls
        calls += 1
        if calls < 2: raise RuntimeError("retry me")
        return MOCK_CLASSIFY

    activities = [a for a in ALL_MOCKS if a.__temporal_activity_definition.name != "ClassifyIncident"] + [flaky_classify]

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(env.client, task_queue=TASK_QUEUE, workflows=[IncidentWorkflow, ExecuteStepWorkflow], activities=activities):
            result = await env.client.execute_workflow(IncidentWorkflow.run, make_incident(), id="wf-retry", task_queue=TASK_QUEUE)
            assert calls == 2
            assert result["classification"] == MOCK_CLASSIFY
