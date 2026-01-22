"""HTTP server helpers for extracting context and creating server spans."""

from __future__ import annotations

from typing import Dict, Optional

from traccia.context import extract_trace_context
from traccia.tracer.tracer import Tracer
from traccia.tracer.span_context import SpanContext


def extract_parent_context(headers: Dict[str, str]) -> Optional[SpanContext]:
    """Parse traceparent/tracestate from headers and return SpanContext if valid."""
    return extract_trace_context(headers)


def start_server_span(tracer: Tracer, name: str, headers: Dict[str, str], attributes=None):
    """
    Convenience helper to start a server span with extracted parent context.

    Returns the span context manager (caller should use 'with' or 'async with').
    """
    parent_ctx = extract_parent_context(headers)
    return tracer.start_as_current_span(name, attributes=attributes, parent_context=parent_ctx)

