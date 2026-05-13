import datetime
import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
import api.server as server_module
from api.server import app

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

def mock_tc(monkeypatch):
    tc = MagicMock()
    handle = MagicMock()
    # Use a real string for status.name to avoid empty dict serialization in tests
    status = MagicMock()
    status.name = "RUNNING"
    handle.describe = AsyncMock(return_value=MagicMock(status=status, start_time=datetime.datetime.now()))
    handle.result = AsyncMock(return_value={"status": "done"})
    handle.signal = AsyncMock(return_value=None)
    tc.start_workflow = AsyncMock(return_value=handle)
    tc.get_workflow_handle = MagicMock(return_value=handle)
    monkeypatch.setattr(server_module, "temporal_client", tc)
    return tc, handle

async def test_health_endpoint(client, monkeypatch):
    # Connected
    mock_tc(monkeypatch)
    resp = await client.get("/health")
    assert resp.json()["temporal_connected"] is True

    # Disconnected
    monkeypatch.setattr(server_module, "temporal_client", None)
    resp = await client.get("/health")
    assert resp.json()["temporal_connected"] is False

async def test_start_incident_flow(client, monkeypatch):
    tc, _ = mock_tc(monkeypatch)
    payload = {"alertId": "123", "severity": "P1", "service": "api", "errorMessage": "err", "runbookTags": []}
    resp = await client.post("/incidents/start", json=payload)
    assert resp.status_code == 200
    assert "workflow_id" in resp.json()
    tc.start_workflow.assert_awaited_once()

async def test_override_signal_flow(client, monkeypatch):
    _, handle = mock_tc(monkeypatch)
    resp = await client.post("/incidents/wf-1/override", json={"action": "rollback", "engineer": "bob"})
    assert resp.status_code == 200
    handle.signal.assert_awaited_once()

async def test_get_status_flow(client, monkeypatch):
    mock_tc(monkeypatch)
    resp = await client.get("/incidents/wf-1/status")
    assert resp.status_code == 200
    assert resp.json()["status"] == "RUNNING"
