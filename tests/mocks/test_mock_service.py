import pytest
import importlib.util
from pathlib import Path
from httpx import AsyncClient, ASGITransport

_ROOT = Path(__file__).parent.parent.parent
_spec = importlib.util.spec_from_file_location("mock_service_server", _ROOT / "mock-service" / "server.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
app = _mod.app

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

async def test_mock_service_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"
