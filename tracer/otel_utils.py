"""DEPRECATED: Use traccia.utils.helpers instead.

This file is kept for backward compatibility with old adapter code.
All new code should use traccia.utils.helpers.
"""

from __future__ import annotations

# Re-export from utils.helpers for backward compatibility
from traccia.utils.helpers import (
    format_trace_id as otel_trace_id_to_traccia,
    format_span_id as otel_span_id_to_traccia,
    parse_trace_id as traccia_id_to_otel_trace_id,
    parse_span_id as traccia_id_to_otel_span_id,
)

# Timestamp functions (passthrough)
def otel_timestamp_to_ns(otel_time: int) -> int:
    """Convert OpenTelemetry timestamp to nanoseconds (passthrough)."""
    return otel_time

def ns_to_otel_timestamp(ns: int) -> int:
    """Convert nanoseconds to OpenTelemetry timestamp (passthrough)."""
    return ns
