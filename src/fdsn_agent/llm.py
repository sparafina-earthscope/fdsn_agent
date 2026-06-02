"""Low-level LLM HTTP client — no third-party dependencies."""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fdsn_agent.config import LLMConfig
from fdsn_agent.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

Message = dict[str, str]


def _http_post(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    body = json.dumps(payload).encode()
    req = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())  # type: ignore[no-any-return]
    except HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        raise RuntimeError(f"HTTP {exc.code} from LLM endpoint: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error reaching LLM: {exc.reason}") from exc


def call_llm(messages: list[Message], cfg: LLMConfig) -> str:
    """Send *messages* to the LLM described by *cfg* and return the text reply.

    Handles both Anthropic native format and OpenAI-compatible format
    transparently based on ``cfg.format``.

    Parameters
    ----------
    messages:
        List of ``{"role": ..., "content": ...}`` dicts.  For Anthropic format
        include a ``role="system"`` message; it will be extracted automatically.
    cfg:
        :class:`~fdsn_agent.config.LLMConfig` describing the backend.

    Returns
    -------
    str
        The assistant's text reply.

    Raises
    ------
    RuntimeError
        On HTTP errors or network failures.
    """
    base_url = cfg.base_url.rstrip("/")
    headers: dict[str, str] = {"Content-Type": "application/json"}

    if cfg.api_key:
        if cfg.format == "anthropic":
            headers["x-api-key"] = cfg.api_key
            headers["anthropic-version"] = "2023-06-01"
        else:
            headers["Authorization"] = f"Bearer {cfg.api_key}"

    if cfg.format == "anthropic":
        system_msgs = [m for m in messages if m["role"] == "system"]
        chat_msgs   = [m for m in messages if m["role"] != "system"]
        payload: dict[str, Any] = {
            "model":       cfg.model,
            "max_tokens":  cfg.max_tokens,
            "temperature": cfg.temperature,
            "system":      system_msgs[0]["content"] if system_msgs else SYSTEM_PROMPT,
            "messages":    chat_msgs,
        }
        logger.debug("POST %s/messages model=%s", base_url, cfg.model)
        data = _http_post(f"{base_url}/messages", headers, payload, cfg.timeout)
        return str(data["content"][0]["text"])

    else:  # openai-compatible
        payload = {
            "model":       cfg.model,
            "max_tokens":  cfg.max_tokens,
            "temperature": cfg.temperature,
            "messages":    messages,
        }
        logger.debug("POST %s/chat/completions model=%s", base_url, cfg.model)
        data = _http_post(f"{base_url}/chat/completions", headers, payload, cfg.timeout)
        return str(data["choices"][0]["message"]["content"])
