"""
fdsn_agent — Headless FDSN seismic archive agent.

Quickstart
----------
>>> from fdsn_agent import Agent, LLMConfig
>>> cfg = LLMConfig.from_preset("anthropic", api_key="sk-ant-...")
>>> agent = Agent(cfg)
>>> result = agent.query("Find M6+ earthquakes in Japan in 2024")
>>> print(result.summary)
"""

from fdsn_agent.config import LLMConfig, PRESETS
from fdsn_agent.agent import Agent, AgentResult

__all__ = ["Agent", "AgentResult", "LLMConfig", "PRESETS"]
__version__ = "0.1.0"
