"""Unit tests for FDSN tool modules — HTTP is mocked."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

# ── shared mock helper ────────────────────────────────────────────────────────

def _mock_urlopen(body: str | None, status: int = 200):
    """Return a context-manager mock for urllib.request.urlopen."""
    if body is None:
        from urllib.error import HTTPError
        exc = HTTPError(url="http://x", code=404, msg="No data", hdrs=None, fp=None)
        return patch("fdsn_agent.tools.base.urlopen", side_effect=exc)

    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=cm)
    cm.__exit__  = MagicMock(return_value=False)
    cm.read      = MagicMock(return_value=body.encode())
    return patch("fdsn_agent.tools.base.urlopen", return_value=cm)


# ── station tool ──────────────────────────────────────────────────────────────

STATION_TEXT = (
    "#Network|Station|Latitude|Longitude|Elevation|SiteName|StartTime|EndTime\n"
    "IU|ANMO|34.945|-106.457|1820.0|Albuquerque, New Mexico|1989-08-29T00:00:00|\n"
    "IU|HRV|42.506|-71.558|200.0|Harvard, Massachusetts|1988-01-01T00:00:00|\n"
)

class TestStationTool:
    def test_parses_two_stations(self):
        from fdsn_agent.tools import station
        with _mock_urlopen(STATION_TEXT):
            result = station.run({"network": "IU", "level": "station"})
        assert result["count"] == 2
        s0 = result["stations"][0]
        assert s0["Network"] == "IU"
        assert s0["Station"] == "ANMO"
        assert s0["Latitude"] == "34.945"

    def test_404_returns_empty(self):
        from fdsn_agent.tools import station
        with _mock_urlopen(None):
            result = station.run({"network": "XX"})
        assert result["count"] == 0
        assert result["stations"] == []
        assert "note" in result

    def test_channel_level(self):
        channel_text = (
            "#Network|Station|Location|Channel|Latitude|Longitude|Elevation|Depth|Azimuth|Dip|SensorDescription|Scale|ScaleFreq|ScaleUnits|SampleRate|StartTime|EndTime\n"
            "IU|ANMO|00|BHZ|34.945|-106.457|1820.0|100.0|0.0|-90.0|Streckeisen STS-2|6.27165e+08|0.02|m/s|20.0|1997-01-01T00:00:00|\n"
            "IU|ANMO|00|BHN|34.945|-106.457|1820.0|100.0|0.0|0.0|Streckeisen STS-2|6.27165e+08|0.02|m/s|20.0|1997-01-01T00:00:00|\n"
        )
        from fdsn_agent.tools import station
        with _mock_urlopen(channel_text):
            result = station.run({"network": "IU", "station": "ANMO", "level": "channel"})
        assert result["count"] == 2
        assert result["stations"][0]["Channel"] == "BHZ"


# ── event tool ────────────────────────────────────────────────────────────────

def _make_geojson(events: list[dict]) -> str:
    features = [
        {
            "type": "Feature",
            "id":   e["id"],
            "properties": {
                "mag":     e["mag"],
                "magType": e.get("magType", "mww"),
                "place":   e["place"],
                "time":    e["time"],
                "status":  "reviewed",
                "url":     f"https://earthquake.usgs.gov/earthquakes/eventpage/{e['id']}",
            },
            "geometry": {
                "type":        "Point",
                "coordinates": [e["lon"], e["lat"], e["depth"]],
            },
        }
        for e in events
    ]
    return json.dumps({
        "type":     "FeatureCollection",
        "metadata": {"count": len(features)},
        "features": features,
    })


class TestEventTool:
    def test_parses_events(self):
        gj = _make_geojson([
            {"id": "us7000m9g4", "mag": 7.5, "place": "Noto Peninsula, Japan",
             "time": 1704067200000, "lon": 137.2, "lat": 37.5, "depth": 10.0},
            {"id": "us7000xxxx", "mag": 6.2, "place": "Near Kyoto, Japan",
             "time": 1706745600000, "lon": 135.7, "lat": 35.0, "depth": 15.0},
        ])
        from fdsn_agent.tools import event
        with _mock_urlopen(gj):
            result = event.run({"minmagnitude": "6.0", "starttime": "2024-01-01T00:00:00",
                                "endtime": "2024-12-31T00:00:00"})
        assert result["count"] == 2
        assert result["total_available"] == 2
        e0 = result["events"][0]
        assert e0["id"] == "us7000m9g4"
        assert e0["magnitude"] == 7.5
        assert e0["depth_km"] == 10.0

    def test_404_returns_empty(self):
        from fdsn_agent.tools import event
        with _mock_urlopen(None):
            result = event.run({"minmagnitude": "9.9"})
        assert result["count"] == 0
        assert result["events"] == []

    def test_event_fields_present(self):
        gj = _make_geojson([
            {"id": "x1", "mag": 5.0, "place": "Test", "time": 0,
             "lon": 0.0, "lat": 0.0, "depth": 5.0},
        ])
        from fdsn_agent.tools import event
        with _mock_urlopen(gj):
            result = event.run({})
        e = result["events"][0]
        for key in ("id", "time", "magnitude", "mag_type", "place",
                    "depth_km", "longitude", "latitude", "status", "url"):
            assert key in e, f"missing key: {key}"


# ── dataselect tool ───────────────────────────────────────────────────────────

class TestDataselectTool:
    def test_returns_expected_keys(self):
        from fdsn_agent.tools import dataselect
        result = dataselect.run({
            "network": "IU", "station": "ANMO", "location": "00",
            "channel": "BHZ",
            "starttime": "2024-01-01T00:00:00",
            "endtime":   "2024-01-01T01:00:00",
        })
        assert "query_url"     in result
        assert "obspy_snippet" in result
        assert "curl_command"  in result
        assert "note"          in result

    def test_obspy_snippet_contains_params(self):
        from fdsn_agent.tools import dataselect
        result = dataselect.run({
            "network": "AK", "station": "BMR",
            "starttime": "2024-06-01T00:00:00",
            "endtime":   "2024-06-01T00:10:00",
        })
        snippet = result["obspy_snippet"]
        assert "AK" in snippet
        assert "BMR" in snippet
        assert "UTCDateTime" in snippet

    def test_query_url_contains_network(self):
        from fdsn_agent.tools import dataselect
        result = dataselect.run({"network": "II", "station": "BFO",
                                  "starttime": "2024-01-01T00:00:00",
                                  "endtime": "2024-01-01T00:05:00"})
        assert "II" in result["query_url"]

    def test_no_network_call(self):
        """dataselect.run must not make any HTTP requests."""
        from fdsn_agent.tools import dataselect
        with patch("fdsn_agent.tools.base.urlopen") as mock_open:
            dataselect.run({"network": "IU", "station": "ANMO",
                            "starttime": "2024-01-01T00:00:00",
                            "endtime": "2024-01-01T01:00:00"})
        mock_open.assert_not_called()
