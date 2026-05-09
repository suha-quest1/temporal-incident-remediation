"""Shared fixtures for the entire test suite."""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

from temporal.data.data_class import IncidentDetails, OverrideSignal

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def test_incident() -> IncidentDetails:
    return IncidentDetails(
        alertId="test-alert-001",
        severity="critical",
        service="backend-api",
        errorMessage="OOMKilled pod backend-api: container exceeded memory limit",
        runbookTags=["OOM", "memory", "kubernetes"],
    )


@pytest.fixture
def rollback_signal() -> OverrideSignal:
    return OverrideSignal(action="rollback", engineer="sre-alice")


@pytest.fixture
def approve_signal() -> OverrideSignal:
    return OverrideSignal(action="approve", engineer="sre-alice")


def make_groq_mock(content: str) -> MagicMock:
    """Return a mock Groq client whose .chat.completions.create() returns content."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = content
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    return mock_client


@pytest.fixture
def groq_classify_mock():
    return make_groq_mock('{"incident_type": "OOM", "severity": "P1"}')


@pytest.fixture
def groq_plan_mock():
    return make_groq_mock(
        '["kubectl get pods", "kubectl rollout restart deployment/api"]'
    )


@pytest.fixture
def groq_postmortem_mock():
    return make_groq_mock(
        "# Incident Report\n\n## Summary\nOOM incident resolved.\n\n## Actions\n- Restarted pod"
    )


@pytest.fixture
def test_runbook_path() -> Path:
    return FIXTURES_DIR / "runbook.json"


def make_http_mock(json_data: dict, status_code: int = 200) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.json.return_value = json_data
    mock_resp.raise_for_status.return_value = None
    mock_resp.status_code = status_code
    return mock_resp


@pytest.fixture
def mock_k8s_success():
    return make_http_mock(
        {"status": "success", "output": "mock-kubectl executed: kubectl get pods"}
    )


@pytest.fixture
def mock_k8s_failure():
    return make_http_mock({"status": "failed", "output": "error: permission denied"})


@pytest.fixture
def mock_service_healthy():
    return make_http_mock({"status": "healthy"})


@pytest.fixture
def mock_service_unhealthy():
    return make_http_mock({"status": "degraded"})
