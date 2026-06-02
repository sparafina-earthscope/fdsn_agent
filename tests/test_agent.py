"""Tests for the Agent class — LLM and FDSN calls fully mocked."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from fdsn_agent.agent import Agent, AgentResult
from fdsn_agent.config import LLMConfig


def _make_cfg() -> LLMConfig:
    return LLMConfig(base_url="http://mock", model="mock-model", format="openai")


# ── Helpers ───────────────────────────────────────────────────────────────────

TOOL_CALL_REPLY = '{"tool": "fdsn_event", "params": {"minmagnitude": "6.0", "limit": "5"}}'

TOOL_RESULT = {
    "count": 2,
    "total_available": 2,
    "events": [
        {"id": "us001", "magnitude": 7.5, "place": "Japan", "depth_km": 10.0,
         "latitude": 37.5, "longitude": 137.2, "time": 1704067200000,
         "mag_type": "mww", "status": "reviewed", "url": "http://example.com"},
    ],
}

FINAL_REPLY = (
    '{"summary": "Found 2 M6+ events in Japan.", '
    '"data": {"count": 2}, "obspy_snippet": null}'
)

DIRECT_REPLY = (
    '{"summary": "FDSN stands for International Federation of Digital Seismograph Networks.", '
    '"data": null, "obspy_snippet": null}'
)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestAgentQuery:
    def test_tool_call_flow(self):
        cfg   = _make_cfg()
        agent = Agent(cfg)

        with (
            patch("fdsn_agent.agent.call_llm", side_effect=[TOOL_CALL_REPLY, FINAL_REPLY]),
            patch.dict("fdsn_agent.tools.REGISTRY", {"fdsn_event": lambda p: TOOL_RESULT}) as mock_tool,
        ):
            result = agent.query("Find M6+ earthquakes in Japan 2024")

        assert isinstance(result, AgentResult)
        assert result.tool_called  == "fdsn_event"
        assert result.tool_params  == {"minmagnitude": "6.0", "limit": "5"}
        assert result.tool_result  == TOOL_RESULT
        assert result.summary      == "Found 2 M6+ events in Japan."
        assert result.data         == {"count": 2}
        assert result.obspy_snippet is None
        # REGISTRY was replaced with lambda; call check implicit via result assertions

    def test_direct_answer_no_tool(self):
        """LLM answers without calling a tool."""
        cfg   = _make_cfg()
        agent = Agent(cfg)

        with patch("fdsn_agent.agent.call_llm", return_value=DIRECT_REPLY):
            result = agent.query("What does FDSN stand for?")

        assert result.tool_called  is None
        assert result.tool_params  is None
        assert result.tool_result  is None
        assert "Federation" in result.summary

    def test_unknown_tool_raises(self):
        cfg   = _make_cfg()
        agent = Agent(cfg)
        bad_reply = '{"tool": "nonexistent_tool", "params": {}}'

        with patch("fdsn_agent.agent.call_llm", return_value=bad_reply):
            with pytest.raises(ValueError, match="nonexistent_tool"):
                agent.query("Do something unknown")

    def test_station_tool_flow(self):
        station_result = {"count": 1, "stations": [{"Network": "IU", "Station": "ANMO"}]}
        tool_reply     = '{"tool": "fdsn_station", "params": {"network": "IU", "station": "ANMO"}}'
        final          = '{"summary": "ANMO is in Albuquerque.", "data": {"count":1}, "obspy_snippet": null}'

        cfg   = _make_cfg()
        agent = Agent(cfg)

        with (
            patch("fdsn_agent.agent.call_llm", side_effect=[tool_reply, final]),
            patch.dict("fdsn_agent.tools.REGISTRY", {"fdsn_station": lambda p: station_result}),
        ):
            result = agent.query("Tell me about IU.ANMO")

        assert result.tool_called == "fdsn_station"
        assert result.summary     == "ANMO is in Albuquerque."

    def test_dataselect_obspy_snippet_propagated(self):
        snippet      = "from obspy import UTCDateTime\nfrom obspy.clients.fdsn import Client\n\nclient = Client('IRIS')"
        ds_result    = {"query_url": "http://x", "obspy_snippet": snippet,
                        "curl_command": "curl ...", "note": "POST only"}
        tool_reply   = '{"tool": "fdsn_dataselect_info", "params": {"network": "IU", "station": "ANMO", "starttime": "2024-01-01T00:00:00", "endtime": "2024-01-01T01:00:00"}}'
        final        = '{"summary": "Use the ObsPy snippet.", "data": {}, "obspy_snippet": null}'

        cfg   = _make_cfg()
        agent = Agent(cfg)

        with (
            patch("fdsn_agent.agent.call_llm", side_effect=[tool_reply, final]),
            patch.dict("fdsn_agent.tools.REGISTRY", {"fdsn_dataselect_info": lambda p: ds_result}),
        ):
            result = agent.query("Get waveforms for IU.ANMO")

        # snippet should be propagated from tool_result when LLM returns null
        assert result.obspy_snippet == snippet


# ── AgentResult serialisation ─────────────────────────────────────────────────

class TestAgentResult:
    def _make_result(self) -> AgentResult:
        return AgentResult(
            query="test query",
            summary="test summary",
            data={"count": 1},
            tool_called="fdsn_event",
            tool_params={"minmagnitude": "6.0"},
            tool_result={"count": 1, "events": []},
            obspy_snippet=None,
            raw_llm="raw",
        )

    def test_to_dict_keys(self):
        result = self._make_result()
        d = result.to_dict()
        for key in ("query", "summary", "data", "tool_called",
                    "tool_params", "tool_result", "obspy_snippet", "raw_llm"):
            assert key in d

    def test_to_json_round_trip(self):
        import json
        result = self._make_result()
        raw  = result.to_json()
        data = json.loads(raw)
        assert data["query"]   == "test query"
        assert data["summary"] == "test summary"

    def test_to_json_pretty(self):
        result = self._make_result()
        pretty = result.to_json(pretty=True)
        assert "\n" in pretty
        assert "  " in pretty
