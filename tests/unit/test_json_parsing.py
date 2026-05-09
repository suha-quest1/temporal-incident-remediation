"""
Unit tests for the _extract_json helper utility.
This function is critical — if it breaks, all LLM activities break.
"""

import pytest
from temporal.activities import _extract_json


class TestExtractJson:

    def test_clean_json_object(self):
        raw = '{"incident_type": "OOM", "severity": "P1"}'
        assert _extract_json(raw) == raw

    def test_clean_json_array(self):
        raw = '["kubectl get pods", "kubectl describe pod"]'
        assert _extract_json(raw) == raw

    def test_strips_json_code_fence(self):
        raw = '```json\n{"incident_type": "OOM"}\n```'
        result = _extract_json(raw)
        parsed = __import__("json").loads(result)
        assert parsed["incident_type"] == "OOM"

    def test_strips_plain_code_fence(self):
        raw = '```\n["cmd1", "cmd2"]\n```'
        result = _extract_json(raw)
        parsed = __import__("json").loads(result)
        assert parsed == ["cmd1", "cmd2"]

    def test_json_with_prose_before(self):
        raw = 'Here is the classification:\n{"incident_type": "disk", "severity": "P2"}'
        result = _extract_json(raw)
        parsed = __import__("json").loads(result)
        assert parsed["incident_type"] == "disk"

    def test_json_array_with_prose_before(self):
        raw = 'The plan:\n["step1", "step2", "step3"]'
        result = _extract_json(raw)
        parsed = __import__("json").loads(result)
        assert parsed == ["step1", "step2", "step3"]

    def test_nested_json(self):
        raw = '{"outer": {"inner": "value"}, "list": [1, 2]}'
        result = _extract_json(raw)
        parsed = __import__("json").loads(result)
        assert parsed["outer"]["inner"] == "value"

    def test_whitespace_stripped(self):
        raw = '  \n  {"incident_type": "OOM"}  \n  '
        result = _extract_json(raw)
        parsed = __import__("json").loads(result)
        assert parsed["incident_type"] == "OOM"

    def test_passes_through_unparseable(self):
        """If truly unparseable, returns as-is so json.loads can surface the error."""
        raw = "not json at all"
        result = _extract_json(raw)
        assert isinstance(result, str)
