"""
LAYER 4 — Mock service (health probe target) tests.
VerifyResolution polls this endpoint — it must always return {"status": "healthy"}.
"""

import pytest
import importlib.util
from pathlib import Path
from httpx import AsyncClient, ASGITransport

_ROOT = Path(__file__).parent.parent.parent
_spec = importlib.util.spec_from_file_location(
    "mock_service_server", _ROOT / "mock-service" / "server.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
mock_service_app = _mod.app


@pytest.fixture
async def svc_client():
    async with AsyncClient(
        transport=ASGITransport(app=mock_service_app), base_url="http://test"
    ) as c:
        yield c


async def test_health_returns_healthy(svc_client):
    resp = await svc_client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


async def test_health_response_schema(svc_client):
    """VerifyResolution checks data.get('status') == 'healthy'."""
    resp = await svc_client.get("/health")
    data = resp.json()
    assert "status" in data
    assert isinstance(data["status"], str)
