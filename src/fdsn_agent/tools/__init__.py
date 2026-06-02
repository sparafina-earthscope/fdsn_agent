"""FDSN tool registry.

Tools are plain functions with the signature::

    def run(params: dict[str, str]) -> dict: ...

The registry maps the tool name (as emitted by the LLM) to its ``run``
function.  Add new tools here to extend the agent.
"""

from fdsn_agent.tools import dataselect, event, station

REGISTRY: dict[str, object] = {
    "fdsn_station":         station.run,
    "fdsn_event":           event.run,
    "fdsn_dataselect_info": dataselect.run,
}

__all__ = ["REGISTRY"]
