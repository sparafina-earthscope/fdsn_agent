"""LLM backend configuration and provider presets."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal

WireFormat = Literal["anthropic", "openai"]

# ---------------------------------------------------------------------------
# Provider presets
# ---------------------------------------------------------------------------

PRESETS: dict[str, dict[str, str]] = {
    "anthropic":  {
        "base_url": "https://api.anthropic.com/v1",
        "model":    "claude-sonnet-4-20250514",
        "format":   "anthropic",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model":    "gpt-4o",
        "format":   "openai",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "model":    "llama3.1",
        "format":   "openai",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model":    "llama-3.3-70b-versatile",
        "format":   "openai",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "model":    "mistralai/mistral-7b-instruct",
        "format":   "openai",
    },
    "together": {
        "base_url": "https://api.together.xyz/v1",
        "model":    "meta-llama/Llama-3-70b-chat-hf",
        "format":   "openai",
    },
    "vllm": {
        "base_url": "http://localhost:8000/v1",
        "model":    "meta-llama/Meta-Llama-3-8B-Instruct",
        "format":   "openai",
    },
}

# ---------------------------------------------------------------------------
# Config dataclass
# ---------------------------------------------------------------------------

@dataclass
class LLMConfig:
    """All settings needed to call an LLM backend.

    Parameters
    ----------
    base_url:
        The ``/v1`` endpoint base URL (no trailing slash).
    model:
        Model identifier string, e.g. ``"claude-sonnet-4-20250514"``.
    api_key:
        API key.  Leave empty for Ollama / unauthenticated vLLM.
    format:
        Wire format — ``"anthropic"`` or ``"openai"`` (OpenAI-compatible).
    max_tokens:
        Upper bound on LLM response length.
    temperature:
        Sampling temperature.  0.2 works well for tool-use tasks.
    timeout:
        HTTP timeout in seconds for LLM calls.
    """

    base_url:    str
    model:       str
    api_key:     str       = field(default="", repr=False)
    format:      WireFormat = "openai"
    max_tokens:  int       = 1024
    temperature: float     = 0.2
    timeout:     int       = 120

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------

    @classmethod
    def from_preset(
        cls,
        provider: str,
        *,
        api_key: str = "",
        model: str | None = None,
        **kwargs,
    ) -> "LLMConfig":
        """Build a config from a named provider preset.

        Parameters
        ----------
        provider:
            One of the keys in :data:`PRESETS`
            (``"anthropic"``, ``"openai"``, ``"ollama"``, …).
        api_key:
            Override the API key (prefer ``LLM_API_KEY`` env var).
        model:
            Override the default model for this provider.
        **kwargs:
            Any additional :class:`LLMConfig` field values
            (e.g. ``max_tokens=2048``).

        Raises
        ------
        ValueError
            If *provider* is not in :data:`PRESETS`.
        """
        if provider not in PRESETS:
            raise ValueError(
                f"Unknown provider {provider!r}. "
                f"Available: {', '.join(PRESETS)}"
            )
        p = PRESETS[provider]
        return cls(
            base_url=p["base_url"],
            model=model or p["model"],
            api_key=api_key or os.environ.get("LLM_API_KEY", ""),
            format=p["format"],  # type: ignore[arg-type]
            **kwargs,
        )

    @classmethod
    def from_env(cls, provider: str = "openai") -> "LLMConfig":
        """Build a config from environment variables, falling back to a preset.

        Environment variables
        ---------------------
        ``LLM_BASE_URL``, ``LLM_MODEL``, ``LLM_API_KEY``, ``LLM_FORMAT``
        override the corresponding preset values when set.
        """
        preset = PRESETS.get(provider, PRESETS["openai"])
        return cls(
            base_url=os.environ.get("LLM_BASE_URL",  preset["base_url"]),
            model=   os.environ.get("LLM_MODEL",     preset["model"]),
            api_key= os.environ.get("LLM_API_KEY",   ""),
            format=  os.environ.get("LLM_FORMAT",    preset["format"]),  # type: ignore[arg-type]
        )
