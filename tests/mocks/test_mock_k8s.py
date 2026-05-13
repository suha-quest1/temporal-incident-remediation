'''If this was a real application where the kube commands could actually be run, could use actual 
kube pytest commands or kubetest- but since this is a mock, tests are only for policy filtering and command flow'''

import pytest
import importlib.util
from pathlib import Path
from httpx import AsyncClient, ASGITransport

_ROOT = Path(__file__).parent.parent.parent

_spec = importlib.util.spec_from_file_location(
    "mock_k8s_server",
    _ROOT / "mock-k8s" / "server.py",
)

_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

mock_k8s_app = _mod.app


@pytest.fixture
async def k8s_client():
    async with AsyncClient(
        transport=ASGITransport(app=mock_k8s_app),
        base_url="http://test",
    ) as client:
        yield client

@pytest.mark.asyncio
async def test_mock_k8s_health(k8s_client):
    resp = await k8s_client.get("/health")

    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"

@pytest.mark.asyncio
async def test_safe_command_is_processed(k8s_client):
    command = "kubectl rollout restart deployment/api"

    resp = await k8s_client.post(
        "/execute",
        json={"command": command},
    )

    body = resp.json()

    assert resp.status_code == 200
    assert body["status"] == "success"
    assert command in body["output"]

@pytest.mark.asyncio
async def test_dangerous_command_is_rejected(k8s_client):
    command = "kubectl delete --force pod/api"

    resp = await k8s_client.post(
        "/execute",
        json={"command": command},
    )

    body = resp.json()

    assert resp.status_code == 200
    assert body["status"] == "failed"