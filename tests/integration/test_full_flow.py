import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from temporal.workflows import IncidentWorkflow
from temporal.sub_workflow import ExecuteStepWorkflow
from temporal.data.data_class import IncidentDetails, OverrideSignal
from tests.conftest import make_groq_mock, make_http_mock

TASK_QUEUE = "integration-queue"
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"

def make_incident(alert_id="alert-1"):
    return IncidentDetails(alertId=alert_id, severity="critical", service="api", errorMessage="OOM", runbookTags=["OOM"])

class MockHttpCtx:
    def __init__(self, post_resp, get_resp):
        self.inner = MagicMock()
        self.inner.post = AsyncMock(return_value=post_resp)
        self.inner.get = AsyncMock(return_value=get_resp)
    async def __aenter__(self): return self.inner
    async def __aexit__(self, *_): pass

async def test_full_remediation_and_rollback_flow(tmp_path):
    """Validates the entire end-to-end orchestration including branching paths."""
    runbook_file = tmp_path / "runbook.json"
    runbook_file.write_text((FIXTURES_DIR / "runbook.json").read_text())
    
    # Setup multiple Groq responses for a single flow: classify, plan, postmortem
    groq_responses = iter([
        make_groq_mock('{"incident_type": "OOM", "severity": "P1"}'),
        make_groq_mock('{"commands": ["kubectl restart"]}'),
        make_groq_mock("# Postmortem")
    ])
    
    k8s_resp = make_http_mock({"status": "success", "output": "ok"})
    svc_resp = make_http_mock({"status": "healthy"})

    with patch("temporal.activities._RUNBOOK_PATH", runbook_file), \
         patch("temporal.activities._OUTPUT_DIR", tmp_path), \
         patch("temporal.activities.get_groq_client", side_effect=lambda: next(groq_responses)), \
         patch("temporal.activities.httpx.AsyncClient", side_effect=lambda **kw: MockHttpCtx(k8s_resp, svc_resp)):

        async with await WorkflowEnvironment.start_time_skipping() as env:
            from temporal.activities import ClassifyIncident, FetchRunbook, GeneratePlan, ExecuteStep, RollbackChanges, VerifyResolution, GeneratePostmortem
            activities = [ClassifyIncident, FetchRunbook, GeneratePlan, ExecuteStep, RollbackChanges, VerifyResolution, GeneratePostmortem]
            
            async with Worker(env.client, task_queue=TASK_QUEUE, workflows=[IncidentWorkflow, ExecuteStepWorkflow], activities=activities):
                # 1. Test Happy Path (No Rollback)
                result = await env.client.execute_workflow(IncidentWorkflow.run, make_incident("happy"), id="integration-happy", task_queue=TASK_QUEUE)
                assert result["classification"]["incident_type"] == "OOM"
                assert (tmp_path / "postmortem-happy.md").exists()

                # 2. Test Rollback Flow
                # Reset responses for new run
                groq_responses = iter([
                    make_groq_mock('{"incident_type": "OOM", "severity": "P1"}'),
                    make_groq_mock('{"commands": ["kubectl restart"]}'),
                    make_groq_mock("# Postmortem Rollback")
                ])
                
                handle = await env.client.start_workflow(IncidentWorkflow.run, make_incident("rollback"), id="integration-rollback", task_queue=TASK_QUEUE)
                await handle.signal(IncidentWorkflow.humanOverride, OverrideSignal(action="rollback", engineer="alice"))
                result = await handle.result()
                assert result["override_action"] == "rollback"
                assert len(result["rollback_result"]) > 0
