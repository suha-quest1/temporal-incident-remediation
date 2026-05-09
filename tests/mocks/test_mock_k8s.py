import pytest
import importlib.util
from pathlib import Path
from httpx import AsyncClient, ASGITransport

_ROOT = Path(__file__).parent.parent.parent
_spec = importlib.util.spec_from_file_location(
    "mock_k8s_server", _ROOT / "mock-k8s" / "server.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
mock_k8s_app = _mod.app


@pytest.fixture
async def k8s_client():
    async with AsyncClient(
        transport=ASGITransport(app=mock_k8s_app), base_url="http://test"
    ) as c:
        yield c


async def test_mock_k8s_health(k8s_client):
    resp = await k8s_client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


async def test_execute_kubectl_get_pods_succeeds(k8s_client):
    resp = await k8s_client.post("/execute", json={"command": "kubectl get pods"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert "kubectl get pods" in body["output"]


async def test_execute_rollout_restart_succeeds(k8s_client):
    """rollout restart is a valid remediation command and must NOT be rejected."""
    resp = await k8s_client.post(
        "/execute", json={"command": "kubectl rollout restart deployment/api"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"


async def test_execute_describe_pod_succeeds(k8s_client):
    resp = await k8s_client.post(
        "/execute", json={"command": "kubectl describe pod backend-api"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"


async def test_execute_delete_force_is_rejected(k8s_client):
    """delete --force is in FAIL_PATTERNS — should return status=failed."""
    resp = await k8s_client.post(
        "/execute", json={"command": "kubectl delete --force pod/api"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "failed"


async def test_execute_drain_force_is_rejected(k8s_client):
    """drain --force is in FAIL_PATTERNS."""
    resp = await k8s_client.post(
        "/execute", json={"command": "kubectl drain --force node-1"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "failed"


async def test_execute_any_kubectl_command_succeeds(k8s_client):
    for cmd in [
        "kubectl top pods -n default",
        "kubectl get svc -n default",
        "kubectl set resources deployment api --limits=memory=512Mi",
        "kubectl get pvc -n default",
    ]:
        resp = await k8s_client.post("/execute", json={"command": cmd})
        assert resp.json()["status"] == "success", f"Expected success for: {cmd}"


async def test_execute_output_echoes_command(k8s_client):
    """Output must reference the command that was executed."""
    resp = await k8s_client.post("/execute", json={"command": "kubectl get pods"})
    assert "kubectl get pods" in resp.json()["output"]
