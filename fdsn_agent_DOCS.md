# fdsn-agent — Developer and Usage Guide

## Contents

1. [Package overview](#1-package-overview)
2. [Repository layout](#2-repository-layout)
3. [Build](#3-build)
4. [Testing](#4-testing)
5. [Publishing to PyPI](#5-publishing-to-pypi)
6. [Installation](#6-installation)
7. [Configuration](#7-configuration)
8. [CLI usage](#8-cli-usage)
9. [Python API](#9-python-api)
10. [Adding a new FDSN tool](#10-adding-a-new-fdsn-tool)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Package overview

`fdsn-agent` is a headless Python package that accepts natural-language queries
about seismic data and translates them into calls against public FDSN web services,
returning structured JSON.

Key design properties:

- **Zero required runtime dependencies** — the entire package uses the Python
  standard library (`urllib`, `json`, `dataclasses`, `argparse`). The optional
  `requests` extra is available for projects that prefer it.
- **Provider-agnostic** — works with Anthropic, OpenAI, Ollama, Groq, OpenRouter,
  Together AI, vLLM, or any OpenAI-compatible endpoint.
- **Extensible tool registry** — adding support for a new FDSN service is a
  single file plus a one-line registry entry.
- **Fully testable offline** — all network calls are behind thin wrappers that
  are straightforward to mock; the test suite makes no real HTTP requests.

---

## 2. Repository layout

```
fdsn-agent/
├── pyproject.toml              # build metadata, dependency declarations, tool config
├── README.md                   # short install + quickstart
├── DOCS.md                     # this file
├── src/
│   └── fdsn_agent/
│       ├── __init__.py         # public surface: Agent, AgentResult, LLMConfig, PRESETS
│       ├── agent.py            # Agent class and AgentResult dataclass
│       ├── cli.py              # fdsn-agent console script entry point
│       ├── config.py           # LLMConfig dataclass and provider presets
│       ├── llm.py              # HTTP client for Anthropic and OpenAI-compatible APIs
│       ├── parsing.py          # extract_tool_call(), extract_final_response()
│       ├── prompts.py          # SYSTEM_PROMPT constant
│       └── tools/
│           ├── __init__.py     # REGISTRY: maps tool name → run() function
│           ├── base.py         # fdsn_get() shared HTTP helper
│           ├── station.py      # fdsn_station — IRIS station service
│           ├── event.py        # fdsn_event — USGS event service
│           └── dataselect.py   # fdsn_dataselect_info — waveform code generation
└── tests/
    ├── test_agent.py           # Agent class with mocked LLM and tool registry
    ├── test_config.py          # LLMConfig constructors and env-var resolution
    ├── test_parsing.py         # extract_tool_call / extract_final_response
    └── test_tools.py           # FDSN tool modules with mocked urllib
```

### Module responsibilities

| Module | Responsibility |
|---|---|
| `agent.py` | Orchestrates the plan → call → interpret loop; owns `AgentResult` |
| `cli.py` | Parses `argparse` arguments; calls `Agent.query()`; prints JSON |
| `config.py` | `LLMConfig` dataclass; `from_preset()` and `from_env()` constructors |
| `llm.py` | Single `call_llm()` function; handles both wire formats |
| `parsing.py` | Brace-walking JSON extractors; no LLM-format knowledge |
| `prompts.py` | `SYSTEM_PROMPT` string; edit here to adjust tool schema or response format |
| `tools/` | One module per FDSN service; each exports `run(params) -> dict` |

---

## 3. Build

### Prerequisites

- Python 3.11 or 3.12
- `pip` 23+
- `build` (for creating distribution archives)

```bash
pip install --upgrade pip build
```

### Development install (editable)

An editable install lets you modify source files and see changes immediately
without reinstalling.

```bash
git clone https://github.com/spara-earthscope/fdsn-agent
cd fdsn-agent

# Install package + dev tools (pytest, mypy, ruff, responses)
pip install -e ".[dev]"

# Verify
fdsn-agent --list-providers
python -c "from fdsn_agent import Agent; print('ok')"
```

### Build a distribution archive

```bash
# Produces dist/fdsn_agent-0.1.0.tar.gz  and  dist/fdsn_agent-0.1.0-py3-none-any.whl
python -m build
```

`build` runs in an isolated virtual environment, so it only picks up declared
dependencies and will fail if any are accidentally missing.

### Bump the version

Version is declared in exactly one place:

```toml
# pyproject.toml
[project]
version = "0.2.0"
```

and mirrored in:

```python
# src/fdsn_agent/__init__.py
__version__ = "0.2.0"
```

Update both before building a release.

---

## 4. Testing

### Run the full suite

```bash
pytest
```

All 41 tests pass with no network access — FDSN endpoints and the LLM API are
fully mocked.

### Run with coverage

```bash
pytest --cov=fdsn_agent --cov-report=term-missing
```

### Run a subset

```bash
pytest tests/test_tools.py               # FDSN tool modules only
pytest tests/test_agent.py -k "station"  # tests whose name contains 'station'
pytest -x                                # stop on first failure
```

### Linting and type checking

```bash
ruff check src/ tests/     # lint
ruff format --check src/   # format check (no changes)
mypy src/                  # type check
```

To auto-fix lint and format issues:

```bash
ruff check --fix src/ tests/
ruff format src/ tests/
```

### How the mocks work

FDSN HTTP calls go through `fdsn_agent.tools.base.urlopen`. Tests patch this
at the `urllib.request.urlopen` level inside that module:

```python
from unittest.mock import patch, MagicMock

def _mock_urlopen(body: str):
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=cm)
    cm.__exit__  = MagicMock(return_value=False)
    cm.read      = MagicMock(return_value=body.encode())
    return patch("fdsn_agent.tools.base.urlopen", return_value=cm)

def test_something():
    from fdsn_agent.tools import station
    with _mock_urlopen("#Network|Station|...\nIU|ANMO|..."):
        result = station.run({"network": "IU"})
    assert result["count"] == 1
```

LLM calls in agent tests are patched at `fdsn_agent.agent.call_llm`, and the
tool registry is replaced via `patch.dict("fdsn_agent.tools.REGISTRY", {...})`.

---

## 5. Publishing to PyPI

### One-time setup

```bash
pip install twine
```

Register an account at [pypi.org](https://pypi.org) and create an API token
under Account Settings → API tokens.

Store the token in `~/.pypirc`:

```ini
[pypi]
username = __token__
password = pypi-AgEIcHlwaS5vcm...
```

Or pass it on the command line with `--password`.

### Test against TestPyPI first

```bash
python -m build

# Upload to the test index
twine upload --repository testpypi dist/*

# Install from TestPyPI to verify
pip install --index-url https://test.pypi.org/simple/ fdsn-agent
fdsn-agent --list-providers
```

### Publish to PyPI

```bash
twine upload dist/*
```

After upload the package is immediately available:

```bash
pip install fdsn-agent
```

### GitHub Actions release workflow

Create `.github/workflows/release.yml`:

```yaml
name: Release

on:
  push:
    tags: ["v*"]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install build twine
      - run: python -m build
      - run: twine upload dist/*
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
```

Set `PYPI_API_TOKEN` in the repository's Secrets → Actions settings.
Tag a release to trigger it:

```bash
git tag v0.1.0
git push origin v0.1.0
```

---

## 6. Installation

### From PyPI

```bash
pip install fdsn-agent
```

### From source

```bash
pip install git+https://github.com/spara-earthscope/fdsn-agent.git
```

### In a conda environment (GeoLab / EarthScope)

```bash
conda activate my-env
pip install fdsn-agent        # no conda-forge package yet; pip into the env
```

### Verify

```bash
fdsn-agent --list-providers
python -c "import fdsn_agent; print(fdsn_agent.__version__)"
```

---

## 7. Configuration

### LLMConfig

All settings are held in a `LLMConfig` dataclass.

```python
from fdsn_agent import LLMConfig

# Fields and their defaults
LLMConfig(
    base_url    = "...",          # required
    model       = "...",          # required
    api_key     = "",             # optional; leave blank for Ollama / unauthenticated vLLM
    format      = "openai",       # "anthropic" | "openai"
    max_tokens  = 1024,
    temperature = 0.2,            # low temperature improves tool-call reliability
    timeout     = 120,            # seconds
)
```

### Provider presets

```python
from fdsn_agent import LLMConfig, PRESETS

print(list(PRESETS))
# ['anthropic', 'openai', 'ollama', 'groq', 'openrouter', 'together', 'vllm']

cfg = LLMConfig.from_preset("anthropic", api_key="sk-ant-...")
cfg = LLMConfig.from_preset("ollama", model="llama3.1")
cfg = LLMConfig.from_preset("groq", api_key="gsk_...", max_tokens=2048)
```

### Environment variables

`LLMConfig.from_env()` reads these variables, falling back to the named preset:

| Variable | Description | Example |
|---|---|---|
| `LLM_BASE_URL` | API base URL | `http://localhost:11434/v1` |
| `LLM_MODEL` | Model name | `llama3.1` |
| `LLM_API_KEY` | API key | `sk-ant-...` |
| `LLM_FORMAT` | Wire format | `anthropic` or `openai` |

```bash
export LLM_BASE_URL=https://api.anthropic.com/v1
export LLM_MODEL=claude-sonnet-4-20250514
export LLM_API_KEY=sk-ant-...
export LLM_FORMAT=anthropic

fdsn-agent "Find M6+ earthquakes in Japan 2024"
```

### Per-provider notes

**Anthropic** — uses `x-api-key` header and the native `/v1/messages` endpoint.
The `format` must be `"anthropic"`.

**Ollama** — no API key required. Start the server with CORS enabled:
`OLLAMA_ORIGINS=* ollama serve`. Recommended models for tool-following accuracy:
`llama3.1`, `qwen2.5:14b`.

**vLLM** — no API key required by default. Start with `--allowed-origins '["*"]'`
if calling from a browser. The `format` must be `"openai"`.

**Groq / OpenRouter / Together AI** — all use Bearer token authentication
and the OpenAI-compatible format.

---

## 8. CLI usage

### Synopsis

```
fdsn-agent [OPTIONS] QUERY
fdsn-agent [OPTIONS] -          # read query from stdin
```

### Options

| Flag | Default | Description |
|---|---|---|
| `--provider` | `openai` | Provider preset name |
| `--base-url` | *(from preset)* | Override API base URL |
| `--model` | *(from preset)* | Override model name |
| `--api-key` | `LLM_API_KEY` env | API key |
| `--format` | *(from preset)* | `anthropic` or `openai` |
| `--max-tokens` | `1024` | Max LLM response tokens |
| `--temperature` | `0.2` | Sampling temperature |
| `--pretty` | off | Pretty-print JSON output |
| `-v` / `--verbose` | off | Log agent steps to stderr |
| `--list-providers` | — | Print provider presets and exit |

### Examples

#### List all providers

```bash
fdsn-agent --list-providers
```

#### Earthquake catalog

```bash
export LLM_API_KEY=sk-ant-...

fdsn-agent --provider anthropic --pretty \
  "Find M6+ earthquakes in Japan in 2024"
```

Output:

```json
{
  "query": "Find M6+ earthquakes in Japan in 2024",
  "tool_called": "fdsn_event",
  "tool_params": {
    "minmagnitude": "6.0",
    "starttime": "2024-01-01T00:00:00",
    "endtime": "2024-12-31T23:59:59",
    "minlatitude": "30",
    "maxlatitude": "46",
    "minlongitude": "129",
    "maxlongitude": "146",
    "limit": "20"
  },
  "summary": "Found 14 M6.0+ earthquakes in Japan during 2024. The largest was the M7.5 Noto Peninsula event on 1 January at 10 km depth ...",
  "data": {
    "count": 14,
    "total_available": 14,
    "events": [ ... ]
  },
  "obspy_snippet": null,
  "raw_llm": "..."
}
```

#### Station metadata

```bash
fdsn-agent --provider groq --pretty \
  "What broadband channels does IU.ANMO have?"
```

#### Radial station search

```bash
fdsn-agent --provider ollama --model llama3.1 \
  "Find broadband stations within 200 km of Anchorage, Alaska"
```

#### Waveform access

```bash
fdsn-agent --provider anthropic --pretty \
  "Get waveforms for the 2024 Noto Peninsula earthquake at IU.MAJO"
```

The `obspy_snippet` field in the result contains ready-to-run ObsPy code:

```python
from obspy import UTCDateTime
from obspy.clients.fdsn import Client

client = Client('IRIS')
st = client.get_waveforms(
    network='IU',
    station='MAJO',
    location='00',
    channel='BHZ',
    starttime=UTCDateTime('2024-01-01T07:10:00'),
    endtime=UTCDateTime('2024-01-01T08:10:00'),
)
st.plot()
```

#### Stdin / pipe

```bash
# Single query from pipe
echo "Recent seismicity near the Cascadia subduction zone" \
  | fdsn-agent --provider groq --pretty -

# Batch processing from a file
cat queries.txt | while read q; do
  fdsn-agent --provider ollama "$q" >> results.ndjson
done
```

#### Extract a field with jq

```bash
fdsn-agent --provider anthropic \
  "M7+ earthquakes globally in 2024" \
  | jq '.data.events[] | {place, magnitude}'
```

#### Debug mode

```bash
fdsn-agent --provider anthropic -v "Stations near Hokkaido" 2>debug.log
```

The `-v` flag writes timestamped agent steps to stderr:

```
[INFO fdsn_agent.agent] Query: Stations near Hokkaido
[INFO fdsn_agent.agent] Tool call: fdsn_station({"latitude": "43.5", ...})
[DEBUG fdsn_agent.agent] Tool result: 892 bytes
```

---

## 9. Python API

### Basic query

```python
from fdsn_agent import Agent, LLMConfig

cfg    = LLMConfig.from_preset("anthropic", api_key="sk-ant-...")
agent  = Agent(cfg)
result = agent.query("Find M6+ earthquakes in Japan in 2024")

print(result.summary)
# "Found 14 M6.0+ earthquakes in Japan during 2024 ..."

print(result.tool_called)
# "fdsn_event"

print(result.data["count"])
# 14
```

### AgentResult fields

| Field | Type | Description |
|---|---|---|
| `query` | `str` | Original query string |
| `summary` | `str` | Plain-English LLM interpretation |
| `data` | `Any` | Structured tool result (dict or list) |
| `tool_called` | `str \| None` | Name of the tool that was invoked |
| `tool_params` | `dict \| None` | Parameters passed to the tool |
| `tool_result` | `dict \| None` | Raw tool return value |
| `obspy_snippet` | `str \| None` | Ready-to-run ObsPy code, when applicable |
| `raw_llm` | `str` | Final raw LLM reply (useful for debugging) |

### Serialisation

```python
# Plain dict
d = result.to_dict()

# JSON string
json_str    = result.to_json()
json_pretty = result.to_json(pretty=True)

# Write to file
import json
with open("result.json", "w") as f:
    f.write(result.to_json(pretty=True))
```

### Use in a notebook

```python
import pandas as pd
from fdsn_agent import Agent, LLMConfig

cfg    = LLMConfig.from_preset("anthropic", api_key="sk-ant-...")
agent  = Agent(cfg)
result = agent.query("List M5+ earthquakes near Cascadia in 2023")

df = pd.DataFrame(result.data["events"])
df["time"] = pd.to_datetime(df["time"], unit="ms")
df.sort_values("magnitude", ascending=False).head(10)
```

### Run the ObsPy snippet

```python
result = agent.query(
    "Get BHZ waveforms for IU.ANMO for the first hour of 2024"
)

if result.obspy_snippet:
    exec(result.obspy_snippet)   # runs the snippet; st is now in scope
    st.plot()
```

### Batch processing

```python
queries = [
    "M6+ events in Alaska in 2023",
    "M6+ events in Chile in 2023",
    "M6+ events in Indonesia in 2023",
]

results = [agent.query(q) for q in queries]

for r in results:
    print(f"{r.query}: {r.data['count']} events")
```

### Error handling

```python
from fdsn_agent import Agent, LLMConfig

cfg   = LLMConfig.from_preset("ollama")
agent = Agent(cfg)

try:
    result = agent.query("Station list for network IU")
except RuntimeError as e:
    # Raised for LLM HTTP errors (bad API key, network timeout)
    # or FDSN service errors (non-404 HTTP status)
    print(f"Network or service error: {e}")
except ValueError as e:
    # Raised when the LLM requests a tool name not in the registry
    print(f"Unknown tool: {e}")
```

### Using environment variables in Python

```python
import os
from fdsn_agent import Agent, LLMConfig

os.environ["LLM_API_KEY"] = "sk-ant-..."

cfg   = LLMConfig.from_env("anthropic")   # reads LLM_* vars, falls back to preset
agent = Agent(cfg)
```

---

## 10. Adding a new FDSN tool

The agent discovers tools through the `REGISTRY` dict in
`src/fdsn_agent/tools/__init__.py`. Adding a new service takes three steps.

### Step 1 — Write the tool module

Create `src/fdsn_agent/tools/availability.py`:

```python
"""FDSNWS availability tool."""

from fdsn_agent.tools.base import fdsn_get

AVAILABILITY_URL = "https://service.iris.edu/irisws/availability/1/query"


def run(params: dict[str, str]) -> dict:
    """Query the IRIS availability service for data extents."""
    qp = {**params, "format": "geocsv", "nodata": "404"}
    raw = fdsn_get(AVAILABILITY_URL, qp)

    if raw is None:
        return {"count": 0, "extents": [], "note": "No availability data found."}

    lines = [l for l in raw.splitlines() if l and not l.startswith("#")]
    if not lines:
        return {"count": 0, "extents": []}

    header = [h.strip() for h in lines[0].split("|")]
    extents = [
        dict(zip(header, [c.strip() for c in line.split("|")]))
        for line in lines[1:]
    ]
    return {"count": len(extents), "extents": extents}
```

### Step 2 — Register it

In `src/fdsn_agent/tools/__init__.py`, add one line:

```python
from fdsn_agent.tools import availability, dataselect, event, station

REGISTRY: dict[str, object] = {
    "fdsn_station":         station.run,
    "fdsn_event":           event.run,
    "fdsn_dataselect_info": dataselect.run,
    "fdsn_availability":    availability.run,    # ← new
}
```

### Step 3 — Describe it in the system prompt

In `src/fdsn_agent/prompts.py`, add to the tool reference section:

```
fdsn_availability  —  IRIS availability service — data extents by channel
  params: network, station, location, channel, starttime, endtime,
          orderby (nslc_time_quality_samplerate | timespancount | timespancount_desc | latestupdate)
```

The agent will now route availability queries to the new tool without any
other changes.

---

## 11. Troubleshooting

### `ModuleNotFoundError: No module named 'fdsn_agent'`

The package is not installed. Run:

```bash
pip install -e .           # from source
# or
pip install fdsn-agent     # from PyPI
```

### `RuntimeError: HTTP 401 from LLM endpoint`

The API key is missing or wrong. Check:

```bash
echo $LLM_API_KEY          # must be set
fdsn-agent --list-providers  # verify format for your provider
```

For Anthropic the format must be `anthropic`; for all others it is `openai`.

### `RuntimeError: Network error reaching LLM: [Errno 111] Connection refused`

Ollama or vLLM is not running, or the `--base-url` is wrong. Check:

```bash
curl http://localhost:11434/api/tags   # Ollama health check
curl http://localhost:8000/v1/models   # vLLM health check
```

### The LLM returns prose instead of a tool call

The model is not following the system prompt. Try:

- Lowering temperature: `--temperature 0.1`
- Increasing max tokens: `--max-tokens 2048`
- Using a larger model (7B → 14B → 70B)
- For Ollama: switch from `mistral` to `llama3.1` or `qwen2.5:14b`

Run with `-v` to see the raw LLM output:

```bash
fdsn-agent -v --provider ollama "Stations near Seattle" 2>&1 | head -20
```

### FDSN returns no data

The query constraints may be too tight. Common issues:

- Time range too short for the requested area
- Magnitude threshold too high for the region
- Network or station code misspelled (codes are case-sensitive: `IU` not `iu`)
- Geographic bounding box does not cover the target area

### `pytest` — 403 Forbidden on FDSN calls

The test environment does not have access to IRIS or USGS. All tests mock
network calls, so this should not occur. If a test is making real network
calls, the `patch` target is incorrect — verify it matches the import path
in `fdsn_agent.tools.base`.

### Build fails with `ModuleNotFoundError: No module named 'setuptools.backends'`

Upgrade setuptools:

```bash
pip install --upgrade setuptools
```

Or use the compatible build backend already in `pyproject.toml`:

```toml
[build-system]
build-backend = "setuptools.build_meta"
```
