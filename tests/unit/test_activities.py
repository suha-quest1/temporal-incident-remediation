"""
LAYER 1 — Unit tests for all Temporal activities.
All external I/O (Groq, httpx, filesystem) is mocked.
Activities are called directly as async functions — no Temporal server needed.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock, mock_open

from tests.conftest import make_groq_mock, make_http_mock


class TestClassifyIncident:

    async def test_success_returns_classification(self, groq_classify_mock):
        from temporal.activities import ClassifyIncident

        with patch(
            "temporal.activities.get_groq_client", return_value=groq_classify_mock
        ):
            result = await ClassifyIncident("OOMKilled pod backend-api")
        assert result["incident_type"] == "OOM"
        assert result["severity"] == "P1"

    async def test_groq_called_with_truncated_message(self, groq_classify_mock):
        from temporal.activities import ClassifyIncident

        long_msg = "x" * 500
        with patch(
            "temporal.activities.get_groq_client", return_value=groq_classify_mock
        ):
            await ClassifyIncident(long_msg)
        call_args = groq_classify_mock.chat.completions.create.call_args
        prompt = call_args[1]["messages"][0]["content"]
        # Input capped at 300 chars
        assert "x" * 301 not in prompt

    async def test_malformed_json_raises(self):
        from temporal.activities import ClassifyIncident

        mock_client = make_groq_mock("This is not valid JSON at all.")
        with patch("temporal.activities.get_groq_client", return_value=mock_client):
            with pytest.raises(Exception):
                await ClassifyIncident("some error")

    async def test_groq_exception_raises(self):
        from temporal.activities import ClassifyIncident

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("Groq down")
        with patch("temporal.activities.get_groq_client", return_value=mock_client):
            with pytest.raises(Exception):
                await ClassifyIncident("OOMKilled")

    async def test_missing_keys_in_response_raises(self):
        from temporal.activities import ClassifyIncident

        mock_client = make_groq_mock('{"type": "OOM"}')  # missing "severity"
        with patch("temporal.activities.get_groq_client", return_value=mock_client):
            with pytest.raises(Exception):
                await ClassifyIncident("OOMKilled")


class TestFetchRunbook:

    async def test_matches_by_incident_type_key(self, test_runbook_path):
        from temporal.activities import FetchRunbook

        with patch("temporal.activities._RUNBOOK_PATH", test_runbook_path):
            result = await FetchRunbook(["OOM", "memory"])
        assert "kubectl" in result
        assert len(result) > 0

    async def test_matches_by_tag(self, test_runbook_path):
        from temporal.activities import FetchRunbook

        with patch("temporal.activities._RUNBOOK_PATH", test_runbook_path):
            result = await FetchRunbook(["networking", "ingress"])
        assert "kubectl" in result

    async def test_no_match_returns_empty_string(self, test_runbook_path):
        from temporal.activities import FetchRunbook

        with patch("temporal.activities._RUNBOOK_PATH", test_runbook_path):
            result = await FetchRunbook(["completely-unknown-tag-xyz"])
        assert result == ""

    async def test_file_not_found_returns_empty_string(self):
        from temporal.activities import FetchRunbook

        with patch("temporal.activities._RUNBOOK_PATH", Path("/nonexistent/path.json")):
            result = await FetchRunbook(["OOM"])
        assert result == ""

    async def test_caps_at_six_steps(self, tmp_path):
        from temporal.activities import FetchRunbook

        # Runbook with 10 solutions
        big_runbook = {
            "OOM": {"tags": ["oom"], "solution": [f"cmd-{i}" for i in range(10)]}
        }
        runbook_file = tmp_path / "big.json"
        runbook_file.write_text(json.dumps(big_runbook))
        with patch("temporal.activities._RUNBOOK_PATH", runbook_file):
            result = await FetchRunbook(["OOM"])
        # Result is joined by "; " — max 6 steps
        assert result.count(";") <= 5


class TestGeneratePlan:

    async def test_success_returns_command_list(self, groq_plan_mock):
        from temporal.activities import GeneratePlan

        with patch("temporal.activities.get_groq_client", return_value=groq_plan_mock):
            result = await GeneratePlan("OOM", "kubectl rollout restart", "P1")
        assert isinstance(result, list)
        assert len(result) >= 1
        assert all(isinstance(cmd, str) for cmd in result)

    async def test_caps_at_five_commands(self):
        from temporal.activities import GeneratePlan

        mock_client = make_groq_mock('["a","b","c","d","e","f","g"]')  # 7 commands
        with patch("temporal.activities.get_groq_client", return_value=mock_client):
            result = await GeneratePlan("OOM", "", "P1")
        assert len(result) <= 5

    async def test_groq_failure_raises(self):
        from temporal.activities import GeneratePlan

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("timeout")
        with patch("temporal.activities.get_groq_client", return_value=mock_client):
            with pytest.raises(Exception):
                await GeneratePlan("OOM", "", "P1")

    async def test_non_list_llm_response_raises(self):
        from temporal.activities import GeneratePlan

        mock_client = make_groq_mock('{"commands": ["kubectl get pods"]}')
        with patch("temporal.activities.get_groq_client", return_value=mock_client):
            with pytest.raises(Exception):
                await GeneratePlan("OOM", "", "P1")


class TestExecuteStep:

    async def test_success_returns_dict(self, mock_k8s_success):
        from temporal.activities import ExecuteStep

        mock_http = AsyncMock()
        mock_http.__aenter__.return_value.post = AsyncMock(
            return_value=mock_k8s_success
        )
        with patch("temporal.activities.httpx.AsyncClient", return_value=mock_http):
            result = await ExecuteStep("kubectl get pods")
        assert result["status"] == "success"
        assert result["command"] == "kubectl get pods"
        assert "output" in result

    async def test_mock_k8s_failure_raises(self, mock_k8s_failure):
        from temporal.activities import ExecuteStep

        mock_http = AsyncMock()
        mock_http.__aenter__.return_value.post = AsyncMock(
            return_value=mock_k8s_failure
        )
        with patch("temporal.activities.httpx.AsyncClient", return_value=mock_http):
            with pytest.raises(Exception, match="mock-k8s rejected"):
                await ExecuteStep("kubectl delete --force")

    async def test_connection_error_raises(self):
        from temporal.activities import ExecuteStep

        mock_http = AsyncMock()
        mock_http.__aenter__.return_value.post = AsyncMock(
            side_effect=ConnectionError("mock-k8s unreachable")
        )
        with patch("temporal.activities.httpx.AsyncClient", return_value=mock_http):
            with pytest.raises(Exception):
                await ExecuteStep("kubectl get pods")


class TestRollbackChanges:

    async def test_returns_reversed_log(self):
        from temporal.activities import RollbackChanges

        commands = [
            "kubectl get pods",
            "kubectl describe pod api",
            "kubectl rollout restart deployment/api",
        ]
        result = await RollbackChanges(commands)
        assert len(result) == 3
        # Reversed order
        assert "kubectl rollout restart deployment/api" in result[0]
        assert "kubectl get pods" in result[2]

    async def test_empty_commands_returns_empty(self):
        from temporal.activities import RollbackChanges

        result = await RollbackChanges([])
        assert result == []

    async def test_each_entry_prefixed_with_rollback(self):
        from temporal.activities import RollbackChanges

        result = await RollbackChanges(["kubectl get pods"])
        assert result[0].startswith("rollback:")

    async def test_single_command(self):
        from temporal.activities import RollbackChanges

        result = await RollbackChanges(["kubectl rollout restart deployment/api"])
        assert len(result) == 1
        assert "kubectl rollout restart deployment/api" in result[0]


class TestVerifyResolution:

    async def test_healthy_service(self, mock_service_healthy):
        from temporal.activities import VerifyResolution

        mock_http = AsyncMock()
        mock_http.__aenter__.return_value.get = AsyncMock(
            return_value=mock_service_healthy
        )
        with patch("temporal.activities.httpx.AsyncClient", return_value=mock_http):
            result = await VerifyResolution("backend-api")
        assert result["healthy"] is True
        assert result["service"] == "backend-api"

    async def test_unhealthy_service(self, mock_service_unhealthy):
        from temporal.activities import VerifyResolution

        mock_http = AsyncMock()
        mock_http.__aenter__.return_value.get = AsyncMock(
            return_value=mock_service_unhealthy
        )
        with patch("temporal.activities.httpx.AsyncClient", return_value=mock_http):
            result = await VerifyResolution("backend-api")
        assert result["healthy"] is False

    async def test_connection_failure_returns_unhealthy(self):
        from temporal.activities import VerifyResolution

        mock_http = AsyncMock()
        mock_http.__aenter__.return_value.get = AsyncMock(
            side_effect=ConnectionError("mock-service down")
        )
        with patch("temporal.activities.httpx.AsyncClient", return_value=mock_http):
            result = await VerifyResolution("backend-api")
        assert result["healthy"] is False
        assert "error" in result


class TestGeneratePostmortem:

    async def test_writes_markdown_file(self, tmp_path, groq_postmortem_mock):
        from temporal.activities import GeneratePostmortem

        with patch(
            "temporal.activities.get_groq_client", return_value=groq_postmortem_mock
        ):
            with patch("temporal.activities._OUTPUT_DIR", tmp_path):
                result = await GeneratePostmortem(
                    "test-alert-001",
                    {"incident_type": "OOM", "severity": "P1"},
                    ["kubectl get pods"],
                    [
                        {
                            "command": "kubectl get pods",
                            "status": "success",
                            "output": "pod/api Running",
                        }
                    ],
                    {"service": "backend-api", "healthy": True},
                    None,
                )
        written = tmp_path / "postmortem-test-alert-001.md"
        assert written.exists()
        assert "Incident" in written.read_text()
        assert str(written) == result

    async def test_groq_failure_raises(self, tmp_path):
        from temporal.activities import GeneratePostmortem

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("Groq down")
        with patch("temporal.activities.get_groq_client", return_value=mock_client):
            with patch("temporal.activities._OUTPUT_DIR", tmp_path):
                with pytest.raises(Exception):
                    await GeneratePostmortem(
                        "test-alert-002",
                        {"incident_type": "OOM", "severity": "P2"},
                        [],
                        [],
                        {"service": "api", "healthy": False},
                        None,
                    )

    async def test_override_action_included_in_prompt(self, tmp_path):
        from temporal.activities import GeneratePostmortem

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = (
            "# Report\n\n## Actions\n- rollback executed"
        )
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        with patch("temporal.activities.get_groq_client", return_value=mock_client):
            with patch("temporal.activities._OUTPUT_DIR", tmp_path):
                await GeneratePostmortem(
                    "test-alert-003",
                    {"incident_type": "OOM", "severity": "P1"},
                    ["kubectl rollout restart deployment/api"],
                    [],
                    {"service": "api", "healthy": True},
                    "rollback",
                )
        call_args = mock_client.chat.completions.create.call_args
        prompt = call_args[1]["messages"][0]["content"]
        assert "rollback" in prompt
