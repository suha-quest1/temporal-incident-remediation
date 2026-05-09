"""
LAYER 5 — Integration tests.
End-to-end orchestration tests using Temporal's time-skipping environment.
Activities run with real logic but external I/O (Groq, httpx) is patched.
Validates orchestration correctness as a whole, including file persistence.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from temporal.workflows import IncidentWorkflow
from temporal.sub_workflow import ExecuteStepWorkflow
from temporal.data.data_class import IncidentDetails, OverrideSignal
from tests.conftest import make_groq_mock, make_http_mock

TASK_QUEUE = "integration-test-queue"

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def make_incident(**kwargs) -> IncidentDetails:
    defaults = dict(
        alertId="integration-alert-001",
        severity="critical",
        service="backend-api",
        errorMessage="OOMKilled pod backend-api: container exceeded memory limit 512Mi",
        runbookTags=["OOM", "memory", "kubernetes"],
    )
    return IncidentDetails(**{**defaults, **kwargs})


def make_real_activities(tmp_output_dir: Path, tmp_runbook_path: Path):
    """
    Returns context managers that patch all external I/O so real activities
    can be used in workflow tests without Groq or live services.
    """
    groq_classify = make_groq_mock('{"incident_type": "OOM", "severity": "P1"}')
    groq_plan = make_groq_mock(
        '["kubectl get pods -n default", "kubectl rollout restart deployment/backend-api"]'
    )
    groq_pm = make_groq_mock(
        "# Incident Report\n\n## Summary\nOOM resolved.\n\n## Actions\n- Restarted pod"
    )
    k8s_success = make_http_mock(
        {"status": "success", "output": "mock-kubectl executed"}
    )
    svc_healthy = make_http_mock({"status": "healthy"})

    return [
        patch("temporal.activities._RUNBOOK_PATH", tmp_runbook_path),
        patch("temporal.activities._OUTPUT_DIR", tmp_output_dir),
        patch(
            "temporal.activities.get_groq_client",
            side_effect=[groq_classify, groq_plan, groq_pm],
        ),
        patch(
            "temporal.activities.httpx.AsyncClient",
            side_effect=lambda **kw: _make_http_ctx(k8s_success, svc_healthy),
        ),
    ]


class _make_http_ctx:
    """Context manager that returns different responses for POST vs GET."""

    def __init__(self, post_response, get_response):
        self._post = post_response
        self._get = get_response
        self._inner = MagicMock()
        self._inner.post = AsyncMock(return_value=post_response)
        self._inner.get = AsyncMock(return_value=get_response)

    async def __aenter__(self):
        return self._inner

    async def __aexit__(self, *_):
        pass


async def test_full_flow_with_real_activities(tmp_path):
    """
    Real activities run end-to-end through the full workflow.
    External I/O is patched. Postmortem file is written to tmp_path.
    """
    runbook_file = tmp_path / "runbook.json"
    runbook_file.write_text((FIXTURES_DIR / "runbook.json").read_text())

    from temporal.activities import (
        ClassifyIncident,
        FetchRunbook,
        GeneratePlan,
        ExecuteStep,
        RollbackChanges,
        VerifyResolution,
        GeneratePostmortem,
    )

    groq_responses = iter(
        [
            make_groq_mock('{"incident_type": "OOM", "severity": "P1"}'),
            make_groq_mock(
                '["kubectl get pods -n default", "kubectl rollout restart deployment/backend-api"]'
            ),
            make_groq_mock("# Incident Report\n\n## Summary\nOOM resolved."),
        ]
    )
    k8s_success = make_http_mock(
        {"status": "success", "output": "mock-kubectl executed: kubectl get pods"}
    )
    svc_healthy = make_http_mock({"status": "healthy"})

    with patch("temporal.activities._RUNBOOK_PATH", runbook_file), patch(
        "temporal.activities._OUTPUT_DIR", tmp_path
    ), patch(
        "temporal.activities.get_groq_client", side_effect=lambda: next(groq_responses)
    ), patch(
        "temporal.activities.httpx.AsyncClient",
        side_effect=lambda **kw: _make_http_ctx(k8s_success, svc_healthy),
    ):

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue=TASK_QUEUE,
                workflows=[IncidentWorkflow, ExecuteStepWorkflow],
                activities=[
                    ClassifyIncident,
                    FetchRunbook,
                    GeneratePlan,
                    ExecuteStep,
                    RollbackChanges,
                    VerifyResolution,
                    GeneratePostmortem,
                ],
            ):
                result = await env.client.execute_workflow(
                    IncidentWorkflow.run,
                    make_incident(),
                    id="integration-happy-001",
                    task_queue=TASK_QUEUE,
                )

    # Assert classification
    assert result["classification"]["incident_type"] == "OOM"
    assert result["classification"]["severity"] == "P1"

    # Assert plan
    assert isinstance(result["plan"], list)
    assert len(result["plan"]) >= 1

    # Assert execution
    assert len(result["execution_results"]) == len(result["plan"])
    assert all(ex["status"] == "success" for ex in result["execution_results"])

    # Assert verification
    assert result["verification"]["healthy"] is True

    # Assert postmortem file exists on disk
    pm_file = tmp_path / "postmortem-integration-alert-001.md"
    assert pm_file.exists()
    content = pm_file.read_text()
    assert "Incident" in content


async def test_rollback_flow_with_real_activities(tmp_path):
    """
    Full rollback flow: signal triggers RollbackChanges → VerifyResolution.
    Verifies the branching logic with real activity implementations.
    """
    runbook_file = tmp_path / "runbook.json"
    runbook_file.write_text((FIXTURES_DIR / "runbook.json").read_text())

    from temporal.activities import (
        ClassifyIncident,
        FetchRunbook,
        GeneratePlan,
        ExecuteStep,
        RollbackChanges,
        VerifyResolution,
        GeneratePostmortem,
    )

    groq_responses = iter(
        [
            make_groq_mock('{"incident_type": "OOM", "severity": "P1"}'),
            make_groq_mock(
                '["kubectl get pods", "kubectl rollout restart deployment/api"]'
            ),
            make_groq_mock("# Incident Report\n\n## Actions\n- Rollback executed"),
        ]
    )
    k8s_success = make_http_mock({"status": "success", "output": "executed"})
    svc_healthy = make_http_mock({"status": "healthy"})

    with patch("temporal.activities._RUNBOOK_PATH", runbook_file), patch(
        "temporal.activities._OUTPUT_DIR", tmp_path
    ), patch(
        "temporal.activities.get_groq_client", side_effect=lambda: next(groq_responses)
    ), patch(
        "temporal.activities.httpx.AsyncClient",
        side_effect=lambda **kw: _make_http_ctx(k8s_success, svc_healthy),
    ):

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue=TASK_QUEUE,
                workflows=[IncidentWorkflow, ExecuteStepWorkflow],
                activities=[
                    ClassifyIncident,
                    FetchRunbook,
                    GeneratePlan,
                    ExecuteStep,
                    RollbackChanges,
                    VerifyResolution,
                    GeneratePostmortem,
                ],
            ):
                handle = await env.client.start_workflow(
                    IncidentWorkflow.run,
                    make_incident(alertId="integration-rollback-001"),
                    id="integration-rollback-001",
                    task_queue=TASK_QUEUE,
                )
                await handle.signal(
                    IncidentWorkflow.humanOverride,
                    OverrideSignal(action="rollback", engineer="sre-alice"),
                )
                result = await handle.result()

    assert result["override_action"] == "rollback"
    assert isinstance(result["rollback_result"], list)
    assert len(result["rollback_result"]) > 0
    # Rollback entries reversed
    assert "rollback:" in result["rollback_result"][0]
    assert result["verification"]["healthy"] is True

    # Postmortem still written even after rollback
    pm_file = tmp_path / "postmortem-integration-rollback-001.md"
    assert pm_file.exists()


async def test_orchestration_sequence_is_deterministic(tmp_path):
    """
    Validates that activity call ORDER is correct:
    classify → FetchRunbook → generatePlan → executeSteps → verify → postmortem
    """
    call_order = []
    runbook_file = tmp_path / "runbook.json"
    runbook_file.write_text((FIXTURES_DIR / "runbook.json").read_text())

    @activity.defn(name="ClassifyIncident")
    async def seq_classify(err_msg: str) -> dict:
        call_order.append("classify")
        return {"incident_type": "OOM", "severity": "P1"}

    @activity.defn(name="FetchRunbook")
    async def seq_fetch(tags: list[str]) -> str:
        call_order.append("FetchRunbook")
        return "kubectl rollout restart"

    @activity.defn(name="GeneratePlan")
    async def seq_plan(t: str, r: str, s: str) -> list[str]:
        call_order.append("generatePlan")
        return ["kubectl get pods"]

    @activity.defn(name="ExecuteStep")
    async def seq_exec(command: str) -> dict:
        call_order.append(f"executeStep:{command[:10]}")
        return {"command": command, "status": "success", "output": "ok"}

    @activity.defn(name="RollbackChanges")
    async def seq_rollback(commands: list[str]) -> list[str]:
        call_order.append("rollback")
        return []

    @activity.defn(name="VerifyResolution")
    async def seq_verify(service: str) -> dict:
        call_order.append("verify")
        return {"service": service, "healthy": True}

    @activity.defn(name="GeneratePostmortem")
    async def seq_pm(*args) -> str:
        call_order.append("postmortem")
        return "/tmp/pm.md"

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[IncidentWorkflow, ExecuteStepWorkflow],
            activities=[
                seq_classify,
                seq_fetch,
                seq_plan,
                seq_exec,
                seq_rollback,
                seq_verify,
                seq_pm,
            ],
        ):
            await env.client.execute_workflow(
                IncidentWorkflow.run,
                make_incident(alertId="seq-test-001"),
                id="seq-test-001",
                task_queue=TASK_QUEUE,
            )

    # Verify correct sequence
    assert call_order[0] == "classify"
    assert call_order[1] == "FetchRunbook"
    assert call_order[2] == "generatePlan"
    assert "executeStep" in call_order[3]
    assert call_order[-2] == "verify"
    assert call_order[-1] == "postmortem"
    # rollback must NOT appear in timer-expiry (no-signal) flow
    assert "rollback" not in call_order
