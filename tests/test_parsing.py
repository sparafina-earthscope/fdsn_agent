"""Tests for fdsn_agent.parsing."""

import pytest
from fdsn_agent.parsing import extract_tool_call, extract_final_response


# ── extract_tool_call ─────────────────────────────────────────────────────────

class TestExtractToolCall:
    def test_bare_json(self):
        text = '{"tool": "fdsn_event", "params": {"minmagnitude": "6.0"}}'
        result = extract_tool_call(text)
        assert result is not None
        assert result["tool"] == "fdsn_event"
        assert result["params"]["minmagnitude"] == "6.0"

    def test_prose_before_json(self):
        text = 'I will query the catalog.\n{"tool": "fdsn_station", "params": {"network": "IU"}}\nDone.'
        result = extract_tool_call(text)
        assert result is not None
        assert result["tool"] == "fdsn_station"

    def test_multiline_json(self):
        text = '{\n  "tool": "fdsn_event",\n  "params": {\n    "minmagnitude": "6.0"\n  }\n}'
        result = extract_tool_call(text)
        assert result is not None
        assert result["tool"] == "fdsn_event"

    def test_prose_after_json(self):
        text = '{"tool": "fdsn_event", "params": {"limit": "10"}} — that\'s the call.'
        result = extract_tool_call(text)
        assert result is not None
        assert result["tool"] == "fdsn_event"

    def test_no_tool_key_returns_none(self):
        text = '{"message": "hello", "value": 42}'
        assert extract_tool_call(text) is None

    def test_no_json_returns_none(self):
        assert extract_tool_call("The answer is 42.") is None

    def test_empty_string(self):
        assert extract_tool_call("") is None

    def test_malformed_json_skipped(self):
        text = '{broken json} {"tool": "fdsn_event", "params": {}}'
        result = extract_tool_call(text)
        assert result is not None
        assert result["tool"] == "fdsn_event"

    def test_all_three_tools(self):
        for tool in ("fdsn_station", "fdsn_event", "fdsn_dataselect_info"):
            text = f'{{"tool": "{tool}", "params": {{}}}}'
            result = extract_tool_call(text)
            assert result is not None
            assert result["tool"] == tool


# ── extract_final_response ────────────────────────────────────────────────────

class TestExtractFinalResponse:
    def test_bare_json(self):
        text = '{"summary": "Found 3 events.", "data": {"count": 3}, "obspy_snippet": null}'
        result = extract_final_response(text)
        assert result is not None
        assert result["summary"] == "Found 3 events."
        assert result["data"]["count"] == 3
        assert result["obspy_snippet"] is None

    def test_json_with_prose(self):
        text = 'Here is my analysis:\n{"summary": "2 stations found.", "data": [], "obspy_snippet": null}'
        result = extract_final_response(text)
        assert result is not None
        assert "stations" in result["summary"]

    def test_obspy_snippet_preserved(self):
        snippet = "from obspy import UTCDateTime"
        text = f'{{"summary": "ok", "data": {{}}, "obspy_snippet": "{snippet}"}}'
        result = extract_final_response(text)
        assert result is not None
        assert result["obspy_snippet"] == snippet

    def test_no_summary_key_returns_none(self):
        text = '{"result": "something", "count": 5}'
        assert extract_final_response(text) is None

    def test_empty_string(self):
        assert extract_final_response("") is None
