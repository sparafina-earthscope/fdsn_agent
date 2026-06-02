# fdsn-agent

Headless FDSN seismic archive agent — natural-language queries over any LLM backend, results returned as JSON.

Zero runtime dependencies (stdlib only). Python 3.11+.

## Install

```bash
pip install fdsn-agent          # from PyPI (once published)

# or from source
git clone https://github.com/spara-earthscope/fdsn-agent
cd fdsn-agent
pip install -e .
```

## CLI

```bash
# Anthropic
export LLM_API_KEY=sk-ant-...
fdsn-agent --provider anthropic --pretty "Find M6+ earthquakes in Japan in 2024"

# Ollama (local, no key required)
fdsn-agent --provider ollama --model llama3.1 "Broadband stations within 200 km of Seattle"

# Groq
export LLM_API_KEY=gsk_...
fdsn-agent --provider groq "What channels does IU.ANMO have?"

# Any OpenAI-compatible endpoint
fdsn-agent --base-url http://localhost:8000/v1 --model my-model "Cascadia seismicity 2023"

# Stdin
echo "Noto Peninsula earthquake waveforms" | fdsn-agent --provider anthropic -

# List providers
fdsn-agent --list-providers
```

### Output shape

```json
{
  "query":         "Find M6+ earthquakes in Japan in 2024",
  "tool_called":   "fdsn_event",
  "tool_params":   { "minmagnitude": "6.0", "starttime": "2024-01-01T00:00:00", ... },
  "tool_result":   { "count": 14, "events": [ ... ] },
  "summary":       "Found 14 M6+ events in Japan during 2024 ...",
  "data":          { "count": 14, "events": [ ... ] },
  "obspy_snippet": null,
  "raw_llm":       "..."
}
```

## Python API

```python
from fdsn_agent import Agent, LLMConfig

# Cloud provider
cfg   = LLMConfig.from_preset("anthropic", api_key="sk-ant-...")
agent = Agent(cfg)
result = agent.query("Find M6+ earthquakes in Japan in 2024")

print(result.summary)
print(result.data["count"])
print(result.to_json(pretty=True))

# Local Ollama
cfg   = LLMConfig.from_preset("ollama", model="llama3.1")
agent = Agent(cfg)
result = agent.query("Stations within 100 km of Anchorage, Alaska")
```

### LLMConfig

```python
from fdsn_agent import LLMConfig

# From named preset (anthropic, openai, ollama, groq, openrouter, together, vllm)
cfg = LLMConfig.from_preset("groq", api_key="gsk_...", max_tokens=2048)

# From environment variables (LLM_BASE_URL, LLM_MODEL, LLM_API_KEY, LLM_FORMAT)
cfg = LLMConfig.from_env("ollama")

# Fully manual
cfg = LLMConfig(
    base_url="http://localhost:8000/v1",
    model="meta-llama/Meta-Llama-3-8B-Instruct",
    format="openai",
)
```

## FDSN tools

| Tool | Service | Endpoint |
|---|---|---|
| `fdsn_station` | IRIS FDSNWS station | `service.iris.edu/fdsnws/station/1` |
| `fdsn_event` | USGS FDSNWS event | `earthquake.usgs.gov/fdsnws/event/1` |
| `fdsn_dataselect_info` | IRIS FDSNWS dataselect (code gen only) | — |

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

Apache 2.0
