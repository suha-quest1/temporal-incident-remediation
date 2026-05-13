import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone

from temporal.activities import (
    ClassifyIncident,
    FetchRunbook,
    GeneratePlan,
    ExecuteStep,
    RollbackChanges,
    VerifyResolution,
    GeneratePostmortem,
    _RUNBOOK_PATH
)
from tests.conftest import make_groq_mock, make_http_mock

class TestActivitiesUnit:

    async def test_classify_incident(self):
        mock_client = make_groq_mock('{"incident_type": "OOM", "severity": "P1"}')
        with patch("temporal.activities.get_groq_client", return_value=mock_client):
            result = await ClassifyIncident("OOMKilled pod")
            assert result == {"incident_type": "OOM", "severity": "P1"}

    async def test_fetch_runbook(self, test_runbook_path):
        with patch("temporal.activities._RUNBOOK_PATH", test_runbook_path):
            # Test match and capping logic
            result = await FetchRunbook(["OOM", "memory"])
            assert "kubectl" in result
            assert result.count(";") <= 5

            # Test no match
            assert await FetchRunbook(["unknown"]) == ""

    async def test_generate_plan(self):
        # Success path
        mock_client = make_groq_mock('{"commands": ["cmd1", "cmd2", "cmd3"]}')
        with patch("temporal.activities.get_groq_client", return_value=mock_client):
            result = await GeneratePlan("OOM", "runbook", "P1")
            assert result == ["cmd1", "cmd2", "cmd3"]

        # Failure path - should return fallback
        mock_client.chat.completions.create.side_effect = Exception("Groq error")
        result = await GeneratePlan("OOM", "runbook", "P1")
        assert len(result) >= 3 # Uses fallback

    async def test_execute_step(self, mock_k8s_success, mock_k8s_failure):
        mock_http = AsyncMock()
        with patch("temporal.activities.httpx.AsyncClient", return_value=mock_http):
            # Success
            mock_http.__aenter__.return_value.post.return_value = mock_k8s_success
            result = await ExecuteStep("kubectl get pods")
            assert result["status"] == "success"

            # Failure
            mock_http.__aenter__.return_value.post.return_value = mock_k8s_failure
            with pytest.raises(Exception, match="mock-k8s rejected"):
                await ExecuteStep("kubectl delete")

    async def test_rollback_changes(self):
        cmds = ["cmd1", "cmd2"]
        result = await RollbackChanges(cmds)
        assert result == ["rollback: cmd2", "rollback: cmd1"]

    async def test_verify_resolution(self, mock_service_healthy, mock_service_unhealthy):
        mock_http = AsyncMock()
        with patch("temporal.activities.httpx.AsyncClient", return_value=mock_http):
            # Healthy
            mock_http.__aenter__.return_value.get.return_value = mock_service_healthy
            assert (await VerifyResolution("svc"))["healthy"] is True

            # Unhealthy
            mock_http.__aenter__.return_value.get.return_value = mock_service_unhealthy
            assert (await VerifyResolution("svc"))["healthy"] is False

    async def test_generate_postmortem(self, tmp_path, groq_postmortem_mock):
        with patch("temporal.activities.get_groq_client", return_value=groq_postmortem_mock):
            with patch("temporal.activities._OUTPUT_DIR", tmp_path):
                path = await GeneratePostmortem("id", {}, [], [], {"healthy": True}, "rollback")
                assert Path(path).exists()
                assert "Incident" in Path(path).read_text()
