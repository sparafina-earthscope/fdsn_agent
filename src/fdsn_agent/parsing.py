"""Utilities for extracting structured data from LLM text output."""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)


def extract_tool_call(text: str) -> dict | None:
    """Find and parse the first JSON object containing a ``"tool"`` key.

    Handles multi-line JSON and LLMs that wrap the object in prose.
    Walks every ``{`` in *text* looking for a balanced JSON object.

    Returns
    -------
    dict | None
        The parsed tool-call object, or ``None`` if none is found.
    """
    for start in range(len(text)):
        if text[start] != "{":
            continue
        depth = 0
        for end in range(start, len(text)):
            if text[end] == "{":
                depth += 1
            elif text[end] == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : end + 1]
                    try:
                        obj = json.loads(candidate)
                        if "tool" in obj:
                            logger.debug("Tool call extracted: %s", obj.get("tool"))
                            return obj
                    except json.JSONDecodeError:
                        pass
                    break
    return None


def extract_final_response(text: str) -> dict | None:
    """Find and parse the final structured JSON response from the LLM.

    Looks for a JSON object containing a ``"summary"`` key.

    Returns
    -------
    dict | None
        Parsed response dict, or ``None`` if not found / unparseable.
    """
    # Walk every '{' — same brace-matching approach
    for start in range(len(text)):
        if text[start] != "{":
            continue
        depth = 0
        for end in range(start, len(text)):
            if text[end] == "{":
                depth += 1
            elif text[end] == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : end + 1]
                    try:
                        obj = json.loads(candidate)
                        if "summary" in obj:
                            return obj
                    except json.JSONDecodeError:
                        pass
                    break
    return None
