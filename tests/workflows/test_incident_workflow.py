"""
LAYER 2 — Workflow orchestration tests using Temporal's in-process
time-skipping environment. No real Temporal server required.

Key patterns:
- Mock activities use @activity.defn(name=...) to match workflow's activity references
- WorkflowEnvironment.start_time_skipping() auto-advances past timers
- Signals are sent via handle.signal() after workflow starts
"""

import asyncio
import pytest
from unittest.mock import AsyncMock
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from temporal.workflows import IncidentWorkflow
from temporal.sub_workflow import ExecuteStepWorkflow
from temporal.data.data_class import IncidentDetails, OverrideSignal

MOCK_CLASSIFY = {"incident_type": "OOM", "severity": "P1"}
MOCK_RUNBOOK = "kubectl rollout restart deployment/backend-api"
MOCK_PLAN = ["kubectl get pods", "kubectl rollout restart deployment/backend-api"]
MOCK_EXEC = {
    "command": "kubectl get pods",
    "status": "success",
    "output": "pod/api Running",
}
MOCK_ROLLBACK = [
    "rollback: kubectl rollout restart deployment/backend-api",
    "rollback: kubectl get pods",
]
MOCK_VERIFY = {"service": "backend-api", "healthy": True}
MOCK_PM_PATH = "/app/output/postmortem-test-alert-001.md"


@activity.defn(name="ClassifyIncident")
async def mock_classify(err_msg: str) -> dict:
    return MOCK_CLASSIFY


@activity.defn(name="FetchRunbook")
async def mock_fetch_runbook(tags: list[str]) -> str:
    return MOCK_RUNBOOK


@activity.defn(name="GeneratePlan")
async def mock_GeneratePlan(
    incident_type: str, runbook: str, severity: str
) -> list[str]:
    return MOCK_PLAN


@activity.defn(name="ExecuteStep")
async def mock_ExecuteStep(command: str) -> dict:
    return {**MOCK_EXEC, "command": command}


@activity.defn(name="RollbackChanges")
async def mock_RollbackChanges(commands: list[str]) -> list[str]:
    return MOCK_ROLLBACK


@activity.defn(name="VerifyResolution")
async def mock_VerifyResolution(service: str) -> dict:
    return MOCK_VERIFY


@activity.defn(name="GeneratePostmortem")
async def mock_GeneratePostmortem(
    incident_id, classification, plan, execution_results, verification, override_action
) -> str:
    return MOCK_PM_PATH


ALL_MOCK_ACTIVITIES = [
    mock_classify,
    mock_fetch_runbook,
    mock_GeneratePlan,
    mock_ExecuteStep,
    mock_RollbackChanges,
    mock_VerifyResolution,
    mock_GeneratePostmortem,
]

TASK_QUEUE = "test-incident-queue"


def make_incident(**kwargs) -> IncidentDetails:
    defaults = dict(
        alertId="test-alert-001",
        severity="critical",
        service="backend-api",
        errorMessage="OOMKilled pod backend-api",
        runbookTags=["OOM", "memory"],
    )
    return IncidentDetails(**{**defaults, **kwargs})


async def test_happy_path_completes_successfully():
    """Full remediation flow: classify → runbook → plan → execute → verify → postmortem."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[IncidentWorkflow, ExecuteStepWorkflow],
            activities=ALL_MOCK_ACTIVITIES,
        ):
            result = await env.client.execute_workflow(
                IncidentWorkflow.run,
                make_incident(),
                id="test-happy-001",
                task_queue=TASK_QUEUE,
            )

    assert result["classification"] == MOCK_CLASSIFY
    assert result["plan"] == MOCK_PLAN
    assert len(result["execution_results"]) == len(MOCK_PLAN)
    assert result["verification"] == MOCK_VERIFY
    assert result["postmortem_path"] == MOCK_PM_PATH
    assert result["rollback_result"] is None
    assert result["override_action"] is None


async def test_each_plan_step_executed_as_child_workflow():
    """Every command in the plan must produce a child workflow execution result."""
    plan_with_3 = [
        "kubectl get pods",
        "kubectl describe pod api",
        "kubectl rollout restart deployment/api",
    ]

    @activity.defn(name="GeneratePlan")
    async def plan_3_steps(
        incident_type: str, runbook: str, severity: str
    ) -> list[str]:
        return plan_with_3

    activities = [
        a if a.__wrapped__.__name__ != "GeneratePlan" else plan_3_steps
        for a in ALL_MOCK_ACTIVITIES
    ]
    # Replace GeneratePlan properly
    activities_fixed = [
        a for a in ALL_MOCK_ACTIVITIES if a.__wrapped__.__name__ != "GeneratePlan"
    ]
    activities_fixed.append(plan_3_steps)

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[IncidentWorkflow, ExecuteStepWorkflow],
            activities=activities_fixed,
        ):
            result = await env.client.execute_workflow(
                IncidentWorkflow.run,
                make_incident(alertId="test-steps-001"),
                id="test-steps-001",
                task_queue=TASK_QUEUE,
            )

    assert len(result["execution_results"]) == 3


async def test_timer_expiry_runs_verify_without_rollback():
    """When no signal arrives within 30 min, verify runs directly (no rollback)."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[IncidentWorkflow, ExecuteStepWorkflow],
            activities=ALL_MOCK_ACTIVITIES,
        ):
            result = await env.client.execute_workflow(
                IncidentWorkflow.run,
                make_incident(alertId="test-timer-001"),
                id="test-timer-001",
                task_queue=TASK_QUEUE,
            )

    # Time-skipping auto-expires the 30-min timer
    assert result["override_action"] is None
    assert result["rollback_result"] is None
    assert result["verification"]["healthy"] is True


async def test_rollback_signal_triggers_rollback_then_verify():
    """humanOverride signal with action=rollback must call RollbackChanges then verify."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[IncidentWorkflow, ExecuteStepWorkflow],
            activities=ALL_MOCK_ACTIVITIES,
        ):
            handle = await env.client.start_workflow(
                IncidentWorkflow.run,
                make_incident(alertId="test-rollback-001"),
                id="test-rollback-001",
                task_queue=TASK_QUEUE,
            )
            # Signal is queued and delivered when workflow reaches wait_condition
            await handle.signal(
                IncidentWorkflow.humanOverride,
                OverrideSignal(action="rollback", engineer="sre-alice"),
            )
            result = await handle.result()

    assert result["override_action"] == "rollback"
    assert result["rollback_result"] == MOCK_ROLLBACK
    assert result["verification"] == MOCK_VERIFY


async def test_approve_signal_skips_rollback_runs_verify():
    """action=approve must NOT call rollback — only verify."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[IncidentWorkflow, ExecuteStepWorkflow],
            activities=ALL_MOCK_ACTIVITIES,
        ):
            handle = await env.client.start_workflow(
                IncidentWorkflow.run,
                make_incident(alertId="test-approve-001"),
                id="test-approve-001",
                task_queue=TASK_QUEUE,
            )
            await handle.signal(
                IncidentWorkflow.humanOverride,
                OverrideSignal(action="approve", engineer="sre-alice"),
            )
            result = await handle.result()

    assert result["override_action"] == "approve"
    assert result["rollback_result"] is None  # rollback NOT called
    assert result["verification"] == MOCK_VERIFY


async def test_postmortem_runs_after_rollback():
    """generatePostmortem must always be called regardless of override path."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[IncidentWorkflow, ExecuteStepWorkflow],
            activities=ALL_MOCK_ACTIVITIES,
        ):
            handle = await env.client.start_workflow(
                IncidentWorkflow.run,
                make_incident(alertId="test-pm-rollback-001"),
                id="test-pm-rollback-001",
                task_queue=TASK_QUEUE,
            )
            await handle.signal(
                IncidentWorkflow.humanOverride,
                OverrideSignal(action="rollback", engineer="alice"),
            )
            result = await handle.result()

    assert result["postmortem_path"] == MOCK_PM_PATH


async def test_classify_retry_policy_on_transient_failure():
    """ClassifyIncident has retry_policy(max_attempts=3). Transient failure should retry."""
    call_count = 0

    @activity.defn(name="ClassifyIncident")
    async def flaky_classify(err_msg: str) -> dict:
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise RuntimeError("transient Groq error")
        return MOCK_CLASSIFY

    activities_with_flaky = [
        a for a in ALL_MOCK_ACTIVITIES if a.__wrapped__.__name__ != "ClassifyIncident"
    ]
    activities_with_flaky.append(flaky_classify)

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[IncidentWorkflow, ExecuteStepWorkflow],
            activities=activities_with_flaky,
        ):
            result = await env.client.execute_workflow(
                IncidentWorkflow.run,
                make_incident(alertId="test-retry-001"),
                id="test-retry-001",
                task_queue=TASK_QUEUE,
            )

    assert result["classification"] == MOCK_CLASSIFY
    assert call_count == 2  # Failed once, succeeded on retry


async def test_workflow_result_includes_all_input_fields():
    """The workflow result must echo back classification, runbook, plan."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[IncidentWorkflow, ExecuteStepWorkflow],
            activities=ALL_MOCK_ACTIVITIES,
        ):
            result = await env.client.execute_workflow(
                IncidentWorkflow.run,
                make_incident(),
                id="test-fields-001",
                task_queue=TASK_QUEUE,
            )

    assert "classification" in result
    assert "runbooks" in result
    assert "plan" in result
    assert "execution_results" in result
    assert "verification" in result
    assert "postmortem_path" in result
