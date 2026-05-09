"""
LAYER 3 — FastAPI endpoint tests.
All Temporal client calls are mocked — no running Temporal server needed.
Uses httpx.AsyncClient with ASGI transport for real HTTP serialization testing.
"""

import datetime
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

import api.server as server_module
from api.server import app


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


def _running_desc():
    desc = MagicMock()
    desc.status.name = "RUNNING"
    desc.status.value = 1  # RUNNING
    desc.start_time = datetime.datetime(
        2026, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc
    )
    desc.close_time = None
    return desc


def _completed_desc():
    desc = MagicMock()
    desc.status.name = "COMPLETED"
    desc.status.value = 2  # COMPLETED
    desc.start_time = datetime.datetime(2026, 1, 1, 12, 0, tzinfo=datetime.timezone.utc)
    desc.close_time = datetime.datetime(2026, 1, 1, 12, 5, tzinfo=datetime.timezone.utc)
    return desc


def _make_handle(wf_id="test-wf-001", describe_return=None, result_return=None):
    """
    Returns a MagicMock handle where all async methods are AsyncMock.
    get_workflow_handle is SYNCHRONOUS in Temporal — it just returns a handle object.
    """
    handle = MagicMock()
    handle.id = wf_id
    handle.describe = AsyncMock(return_value=describe_return or _running_desc())
    handle.result = AsyncMock(return_value=result_return)
    handle.signal = AsyncMock(return_value=None)
    return handle


def _make_temporal_client(handle=None):
    """
    Returns a MagicMock Temporal client.
    start_workflow is async; get_workflow_handle is sync.
    """
    tc = MagicMock()
    h = handle or _make_handle()
    tc.start_workflow = AsyncMock(return_value=h)
    tc.get_workflow_handle = MagicMock(return_value=h)
    return tc, h


@pytest.fixture
def mock_tc(monkeypatch):
    tc, handle = _make_temporal_client()
    monkeypatch.setattr(server_module, "temporal_client", tc)
    return tc, handle


@pytest.fixture
def no_temporal(monkeypatch):
    monkeypatch.setattr(server_module, "temporal_client", None)


async def test_health_connected(client, mock_tc):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "temporal_connected": True}


async def test_health_disconnected(client, no_temporal):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["temporal_connected"] is False


async def test_start_incident_returns_workflow_id(client, mock_tc):
    """Server generates a UUID-based workflow_id and returns handle.id."""
    # The server builds: workflow_id = f"incident_{service}_{severity}_{alertId}_{uuid.uuid4().hex[:6]}"
    # then calls start_workflow(id=workflow_id) and returns handle.id.
    # Our mock handle has handle.id = "test-wf-001" — the response must include that.
    tc, handle = mock_tc
    resp = await client.post(
        "/incidents/start",
        json={
            "alertId": "alert-oom-001",
            "severity": "critical",
            "service": "backend-api",
            "errorMessage": "OOMKilled",
            "runbookTags": ["OOM"],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "workflow_id" in body
    assert body["workflow_id"].startswith(
        "incident_backend-api_critical_alert-oom-001_"
    )


async def test_start_incident_unique_ids(client, mock_tc):
    """Two starts with same alertId must produce different workflow IDs."""
    payload = {
        "alertId": "dup",
        "severity": "critical",
        "service": "api",
        "errorMessage": "err",
        "runbookTags": [],
    }
    r1 = await client.post("/incidents/start", json=payload)
    r2 = await client.post("/incidents/start", json=payload)
    assert r1.json()["workflow_id"] != r2.json()["workflow_id"]


async def test_start_incident_503_when_no_temporal(client, no_temporal):
    resp = await client.post(
        "/incidents/start",
        json={
            "alertId": "x",
            "severity": "critical",
            "service": "api",
            "errorMessage": "err",
            "runbookTags": [],
        },
    )
    assert resp.status_code == 503


async def test_start_incident_calls_temporal(client, monkeypatch):
    """Workflow must be started via temporal_client with correctly formatted ID."""
    handle = _make_handle(wf_id="incident_postgres-db_high_alert-reg-001_aabbcc")
    tc, _ = _make_temporal_client(handle)
    monkeypatch.setattr(server_module, "temporal_client", tc)

    resp = await client.post(
        "/incidents/start",
        json={
            "alertId": "alert-reg-001",
            "severity": "high",
            "service": "postgres-db",
            "errorMessage": "timeout",
            "runbookTags": [],
        },
    )
    assert resp.status_code == 200
    wf_id = resp.json()["workflow_id"]
    assert wf_id.startswith("incident_postgres-db_high_alert-reg-001_")
    tc.start_workflow.assert_awaited_once()


async def test_override_sends_signal_and_returns_200(client, mock_tc):
    tc, handle = mock_tc
    resp = await client.post(
        "/incidents/incident-test-001/override",
        json={"action": "rollback", "engineer": "alice"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["action"] == "rollback"
    # Signal was called
    handle.signal.assert_awaited_once()


async def test_override_503_when_no_temporal(client, no_temporal):
    resp = await client.post(
        "/incidents/incident-test-001/override",
        json={"action": "rollback", "engineer": "alice"},
    )
    assert resp.status_code == 503


async def test_override_400_on_rpc_error(client, mock_tc):
    from temporalio.service import RPCError, RPCStatusCode

    _, handle = mock_tc
    handle.signal.side_effect = RPCError("not found", RPCStatusCode.NOT_FOUND, "")
    resp = await client.post(
        "/incidents/nonexistent-workflow/override",
        json={"action": "rollback", "engineer": "alice"},
    )
    assert resp.status_code == 404


async def test_status_running(client, mock_tc):
    resp = await client.get("/incidents/incident-test-001/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "RUNNING"
    assert body["workflow_id"] == "incident-test-001"
    assert body["start_time"] is not None
    assert body["close_time"] is None


async def test_status_completed_includes_result(client, monkeypatch):
    handle = _make_handle(
        wf_id="incident-completed-001",
        describe_return=_completed_desc(),
        result_return={"classification": {"incident_type": "OOM", "severity": "P1"}},
    )
    tc, _ = _make_temporal_client(handle)
    monkeypatch.setattr(server_module, "temporal_client", tc)

    resp = await client.get("/incidents/incident-completed-001/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "COMPLETED"
    assert body["result"] is not None
    assert body["close_time"] is not None


async def test_status_404_on_rpc_error(client, monkeypatch):
    from temporalio.service import RPCError, RPCStatusCode

    handle = _make_handle()
    handle.describe.side_effect = RPCError("not found", RPCStatusCode.NOT_FOUND, "")
    tc, _ = _make_temporal_client(handle)
    monkeypatch.setattr(server_module, "temporal_client", tc)

    resp = await client.get("/incidents/nonexistent/status")
    assert resp.status_code == 404


async def test_status_503_when_no_temporal(client, no_temporal):
    resp = await client.get("/incidents/any/status")
    assert resp.status_code == 503


async def test_postmortem_exact_match(client, tmp_path, monkeypatch, mock_tc):
    monkeypatch.setattr(server_module, "_OUTPUT_DIR", tmp_path)
    (tmp_path / "postmortem-alert-test-001.md").write_text(
        "# Incident Report\n\nOK.", encoding="utf-8"
    )
    resp = await client.get(
        "/incidents/incident_backend-api_critical_alert-test-001_abc123/postmortem"
    )
    assert resp.status_code == 200
    assert "Incident Report" in resp.json()["content"]


async def test_postmortem_fallback_to_latest(client, tmp_path, monkeypatch, mock_tc):
    monkeypatch.setattr(server_module, "_OUTPUT_DIR", tmp_path)
    (tmp_path / "postmortem-totally-different-xyz.md").write_text(
        "# Latest PM", encoding="utf-8"
    )
    resp = await client.get(
        "/incidents/incident_service_severity_totally-different-xyz_123/postmortem"
    )
    assert resp.status_code == 200
    assert "Latest PM" in resp.json()["content"]


async def test_postmortem_unavailable(client, tmp_path, monkeypatch, mock_tc):
    monkeypatch.setattr(server_module, "_OUTPUT_DIR", tmp_path)
    resp = await client.get(
        "/incidents/incident_service_severity_no-pm-001_123/postmortem"
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "waiting_for_postmortem"


async def test_list_incidents_from_temporal(client, monkeypatch):
    handle = _make_handle()
    tc, _ = _make_temporal_client(handle)

    # Mock list_workflows to return an async generator yielding one mock workflow
    async def mock_list_workflows():
        mock_wf = MagicMock()
        mock_wf.id = "incident_backend-api_critical_alert-oom-001_abc"
        mock_wf.run_id = "run-123"
        mock_wf.status.name = "RUNNING"
        mock_wf.workflow_type = "IncidentWorkflow"
        mock_wf.start_time = datetime.datetime.now(datetime.timezone.utc)
        mock_wf.close_time = None
        yield mock_wf

        mock_wf_child = MagicMock()
        mock_wf_child.id = "alert-oom-001-step-0-123"
        mock_wf_child.run_id = "run-456"
        mock_wf_child.status.name = "COMPLETED"
        mock_wf_child.workflow_type = "ExecuteStepWorkflow"
        mock_wf_child.start_time = datetime.datetime.now(datetime.timezone.utc)
        mock_wf_child.close_time = datetime.datetime.now(datetime.timezone.utc)
        yield mock_wf_child

    tc.list_workflows = mock_list_workflows
    monkeypatch.setattr(server_module, "temporal_client", tc)

    resp = await client.get("/incidents")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["workflows"]) == 1
    wf = data["workflows"][0]
    assert wf["workflow_id"] == "incident_backend-api_critical_alert-oom-001_abc"
    assert wf["service"] == "backend-api"
    assert wf["severity"] == "critical"


async def test_list_incidents_503_when_no_temporal(client, no_temporal):
    resp = await client.get("/incidents")
    assert resp.status_code == 503
