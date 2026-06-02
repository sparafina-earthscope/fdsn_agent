"""FDSNWS station service tool."""

from __future__ import annotations

from fdsn_agent.tools.base import fdsn_get

STATION_URL = "https://service.iris.edu/fdsnws/station/1/query"


def run(params: dict[str, str]) -> dict:
    """Query the IRIS FDSNWS station service.

    Parameters
    ----------
    params:
        FDSN station query parameters (network, station, location, channel,
        starttime, endtime, latitude/longitude/maxradius, level, …).

    Returns
    -------
    dict
        ``{"count": int, "stations": list[dict]}``
        Each station dict has keys from the FDSN text header
        (Network, Station, Latitude, Longitude, Elevation, SiteName, …).
    """
    qp = {**params, "format": "text", "nodata": "404"}
    raw = fdsn_get(STATION_URL, qp)

    if raw is None:
        return {"count": 0, "stations": [], "note": "No stations matched the query."}

    all_lines   = [line for line in raw.splitlines() if line.strip()]
    header_line = next((l.lstrip("#") for l in all_lines if l.startswith("#")), None)
    data_lines  = [l for l in all_lines if not l.startswith("#")]

    if not data_lines:
        return {"count": 0, "stations": []}

    header    = [h.strip() for h in (header_line or data_lines[0]).split("|")]
    data_rows = data_lines if header_line else data_lines[1:]

    stations = [
        dict(zip(header, [c.strip() for c in line.split("|")]))
        for line in data_rows
        if line.strip()
    ]
    return {"count": len(stations), "stations": stations}
