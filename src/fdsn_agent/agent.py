"""Core agent logic — plan, execute, interpret."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from fdsn_agent.config import LLMConfig
from fdsn_agent.llm import call_llm, Message
from fdsn_agent.parsing import extract_final_response, extract_tool_call
from fdsn_agent.prompts import SYSTEM_PROMPT
from fdsn_agent.tools import REGISTRY

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    """Structured result returned by :meth:`Agent.query`.

    Attributes
    ----------
    query:
        The original natural-language query.
    summary:
        Plain-English interpretation produced by the LLM.
    data:
        Structured data from the FDSN tool call (may be ``None`` if the
        LLM answered without calling a tool).
    tool_called:
        Name of the FDSN tool that was invoked, or ``None``.
    tool_params:
        Parameters passed to the tool, or ``None``.
    tool_result:
        Raw dict returned by the tool, or ``None``.
    obspy_snippet:
        Ready-to-run ObsPy code string when relevant, otherwise ``None``.
    raw_llm:
        The final raw text reply from the LLM (useful for debugging).
    """

    query:         str
    summary:       str
    data:          Any                   = field(default=None)
    tool_called:   str | None            = field(default=None)
    tool_params:   dict | None           = field(default=None)
    tool_result:   dict | None           = field(default=None)
    obspy_snippet: str | None            = field(default=None)
    raw_llm:       str                   = field(default="", repr=False)

    def to_dict(self) -> dict[str, Any]:
        """Return a plain dict suitable for JSON serialisation."""
        return {
            "query":         self.query,
            "tool_called":   self.tool_called,
            "tool_params":   self.tool_params,
            "tool_result":   self.tool_result,
            "summary":       self.summary,
            "data":          self.data,
            "obspy_snippet": self.obspy_snippet,
            "raw_llm":       self.raw_llm,
        }

    def to_json(self, *, pretty: bool = False) -> str:
        """Serialise to JSON string."""
        return json.dumps(
            self.to_dict(),
            indent=2 if pretty else None,
            ensure_ascii=False,
            default=str,
        )


class Agent:
    """FDSN archive agent.

    Wraps the plan → tool-call → interpret loop and exposes a single
    :meth:`query` method.

    Parameters
    ----------
    config:
        :class:`~fdsn_agent.config.LLMConfig` describing the LLM backend.

    Examples
    --------
    >>> from fdsn_agent import Agent, LLMConfig
    >>> cfg = LLMConfig.from_preset("anthropic", api_key="sk-ant-...")
    >>> agent = Agent(cfg)
    >>> result = agent.query("Find M6+ earthquakes in Japan in 2024")
    >>> print(result.summary)

    Using Ollama locally::

        cfg = LLMConfig.from_preset("ollama", model="llama3.1")
        agent = Agent(cfg)
        result = agent.query("What channels does IU.ANMO have?")
    """

    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def query(self, query: str) -> AgentResult:
        """Run a single natural-language FDSN query.

        The agent sends the query to the LLM, detects a tool call in the
        response, executes the FDSN tool, feeds the result back, and
        returns a structured :class:`AgentResult`.

        Parameters
        ----------
        query:
            Plain-English question about seismic stations, events, or
            waveforms.

        Returns
        -------
        AgentResult

        Raises
        ------
        ValueError
            If the LLM requests an unknown tool.
        RuntimeError
            On LLM HTTP errors or FDSN service errors.
        """
        logger.info("Query: %s", query)
        messages = self._initial_messages(query)

        reply1 = call_llm(messages, self.config)
        logger.debug("LLM reply 1 (%d chars): %s…", len(reply1), reply1[:120])

        tool_call = extract_tool_call(reply1)

        if not tool_call:
            logger.info("No tool call — returning direct answer")
            final = extract_final_response(reply1) or {}
            return AgentResult(
                query=query,
                summary=final.get("summary", reply1.strip()),
                data=final.get("data"),
                obspy_snippet=final.get("obspy_snippet"),
                raw_llm=reply1,
            )

        tool_name   = tool_call["tool"]
        tool_params = tool_call.get("params", {})
        logger.info("Tool call: %s(%s)", tool_name, json.dumps(tool_params))

        if tool_name not in REGISTRY:
            raise ValueError(
                f"LLM requested unknown tool {tool_name!r}. "
                f"Available: {', '.join(REGISTRY)}"
            )

        tool_fn     = REGISTRY[tool_name]
        tool_result = tool_fn(tool_params)  # type: ignore[operator]
        logger.debug("Tool result: %d bytes", len(str(tool_result)))

        messages2 = self._followup_messages(messages, reply1, tool_name, tool_result)
        reply2    = call_llm(messages2, self.config)
        logger.debug("LLM reply 2 (%d chars): %s…", len(reply2), reply2[:120])

        final = extract_final_response(reply2) or {}
        return AgentResult(
            query=query,
            tool_called=tool_name,
            tool_params=tool_params,
            tool_result=tool_result,
            summary=final.get("summary", reply2.strip()),
            data=final.get("data", tool_result),
            obspy_snippet=(
                final.get("obspy_snippet")
                or (tool_result or {}).get("obspy_snippet")
            ),
            raw_llm=reply2,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _initial_messages(self, query: str) -> list[Message]:
        if self.config.format == "anthropic":
            return [{"role": "user", "content": query}]
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": query},
        ]

    def _followup_messages(
        self,
        prior: list[Message],
        assistant_reply: str,
        tool_name: str,
        tool_result: dict,
    ) -> list[Message]:
        feedback = (
            f"Tool '{tool_name}' returned:\n"
            f"{json.dumps(tool_result, indent=2, default=str)}\n\n"
            "Respond with ONLY a JSON object:\n"
            '{"summary": "<plain-English interpretation>", '
            '"data": <tool result>, "obspy_snippet": <string or null>}'
        )
        return [
            *prior,
            {"role": "assistant", "content": assistant_reply},
            {"role": "user",      "content": feedback},
        ]
