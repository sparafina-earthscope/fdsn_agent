"""FDSNWS dataselect tool — waveform availability info and code generation."""

from __future__ import annotations

from urllib.parse import urlencode

DATASELECT_URL = "https://service.iris.edu/fdsnws/dataselect/1/query"


def run(params: dict[str, str]) -> dict:
    """Return waveform availability info and ready-to-run code snippets.

    dataselect requires HTTP POST and is blocked by CORS in browser
    contexts, so this tool constructs the query URL and generates
    ObsPy / curl code rather than fetching data directly.

    Parameters
    ----------
    params:
        Keys: network, station, location, channel, starttime, endtime.

    Returns
    -------
    dict
        ``{"query_url": str, "obspy_snippet": str, "curl_command": str, "note": str}``
    """
    net = params.get("network",   "?")
    sta = params.get("station",   "?")
    loc = params.get("location",  "*")
    cha = params.get("channel",   "HH?")
    t0  = params.get("starttime", "")
    t1  = params.get("endtime",   "")

    query_url = f"{DATASELECT_URL}?{urlencode({**params, 'format': 'miniseed'})}"

    obspy_snippet = (
        "from obspy import UTCDateTime\n"
        "from obspy.clients.fdsn import Client\n"
        "\n"
        "client = Client('IRIS')\n"
        "st = client.get_waveforms(\n"
        f"    network='{net}',\n"
        f"    station='{sta}',\n"
        f"    location='{loc}',\n"
        f"    channel='{cha}',\n"
        f"    starttime=UTCDateTime('{t0}'),\n"
        f"    endtime=UTCDateTime('{t1}'),\n"
        ")\n"
        "st.plot()"
    )

    curl_command = (
        f"curl -o waveforms.mseed \\\n"
        f"  --data 'quality=B' \\\n"
        f"  --data-urlencode 'net={net}' \\\n"
        f"  --data-urlencode 'sta={sta}' \\\n"
        f"  --data-urlencode 'loc={loc}' \\\n"
        f"  --data-urlencode 'cha={cha}' \\\n"
        f"  --data-urlencode 'starttime={t0}' \\\n"
        f"  --data-urlencode 'endtime={t1}' \\\n"
        f"  {DATASELECT_URL}"
    )

    return {
        "query_url":     query_url,
        "obspy_snippet": obspy_snippet,
        "curl_command":  curl_command,
        "note": (
            "dataselect requires HTTP POST — use the ObsPy snippet or curl "
            "command above.  The query_url is for reference only."
        ),
    }
