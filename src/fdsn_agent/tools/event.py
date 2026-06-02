"""FDSNWS event service tool."""

from __future__ import annotations

import json

from fdsn_agent.tools.base import fdsn_get

EVENT_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"


def run(params: dict[str, str]) -> dict:
    """Query the USGS FDSNWS event service.

    Parameters
    ----------
    params:
        FDSN event query parameters (starttime, endtime, minmagnitude,
        latitude/longitude/maxradius, limit, orderby, …).

    Returns
    -------
    dict
        ``{"count": int, "total_available": int | None, "events": list[dict]}``
        Each event dict has keys: id, time (ms epoch), magnitude, mag_type,
        place, depth_km, longitude, latitude, status, url.
    """
    qp = {**params, "format": "geojson", "nodata": "404"}
    raw = fdsn_get(EVENT_URL, qp)

    if raw is None:
        return {"count": 0, "total_available": None, "events": [],
                "note": "No events matched the query."}

    gj = json.loads(raw)
    events = []
    for feature in gj.get("features") or []:
        prop   = feature.get("properties", {})
        coords = (feature.get("geometry") or {}).get("coordinates", [None, None, None])
        events.append({
            "id":         feature.get("id"),
            "time":       prop.get("time"),          # milliseconds since epoch
            "magnitude":  prop.get("mag"),
            "mag_type":   prop.get("magType"),
            "place":      prop.get("place"),
            "depth_km":   coords[2],
            "longitude":  coords[0],
            "latitude":   coords[1],
            "status":     prop.get("status"),
            "url":        prop.get("url"),
        })

    return {
        "count":           len(events),
        "total_available": (gj.get("metadata") or {}).get("count"),
        "events":          events,
    }
