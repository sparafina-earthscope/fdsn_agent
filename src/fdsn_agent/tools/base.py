"""Shared utilities for FDSN tool modules."""

from __future__ import annotations

import logging
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

_USER_AGENT = "fdsn-agent/0.1.0"


def fdsn_get(base_url: str, params: dict[str, str]) -> str | None:
    """Perform a GET request against an FDSN web service.

    Parameters
    ----------
    base_url:
        The service query endpoint (without query string).
    params:
        Query parameters dict.

    Returns
    -------
    str | None
        Response body as text, or ``None`` when the service returns 404
        (no data found).

    Raises
    ------
    RuntimeError
        On non-404 HTTP errors or network failures.
    """
    full_url = f"{base_url}?{urlencode(params)}"
    req = Request(full_url, headers={"User-Agent": _USER_AGENT})
    logger.debug("GET %s", full_url)
    try:
        with urlopen(req, timeout=60) as resp:
            return resp.read().decode(errors="replace")
    except HTTPError as exc:
        if exc.code == 404:
            logger.debug("FDSN 404 (no data) for %s", full_url)
            return None
        detail = exc.read().decode(errors="replace")[:300]
        raise RuntimeError(f"FDSN HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"FDSN network error: {exc.reason}") from exc
