"""HTTP client helpers for context propagation."""

from __future__ import annotations

from typing import Dict

from traccia.context import inject_traceparent, inject_tracestate, get_current_span


def inject_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """
    Inject traceparent/tracestate into the provided headers dict if a current span exists.

    Returns the same headers mapping for convenience.
    """
    span = get_current_span()
    if span:
        inject_traceparent(headers, span.context)
        inject_tracestate(headers, span.context)
    return headers

