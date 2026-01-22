"""Helper functions for OpenTelemetry compatibility."""

from __future__ import annotations

from typing import Optional

from opentelemetry.trace import Span as OTelSpan


def get_duration_ns(span: OTelSpan) -> Optional[int]:
    """
    Get span duration in nanoseconds.
    
    Args:
        span: OpenTelemetry Span instance
    
    Returns:
        Duration in nanoseconds, or None if span hasn't ended
    """
    if span.end_time is None:
        return None
    return span.end_time - span.start_time


def get_parent_span_id(span: OTelSpan) -> Optional[int]:
    """
    Get parent span ID from span context.
    
    Args:
        span: OpenTelemetry Span instance
    
    Returns:
        Parent span ID (int64), or None if no parent
    """
    # OTel doesn't expose parent_span_id directly
    # We need to get it from the span's parent context if available
    # For now, return None - parent relationship is maintained via context
    # This can be enhanced if needed by tracking parent during span creation
    return None


def format_trace_id(trace_id: int) -> str:
    """
    Format OTel trace_id (int64) to hex string.
    
    Args:
        trace_id: OTel trace_id as int64
    
    Returns:
        32-character hex string
    """
    return format(trace_id, '032x')


def format_span_id(span_id: int) -> str:
    """
    Format OTel span_id (int64) to hex string.
    
    Args:
        span_id: OTel span_id as int64
    
    Returns:
        16-character hex string
    """
    return format(span_id, '016x')


def parse_trace_id(hex_string: str) -> int:
    """
    Parse hex string trace_id to OTel int64.
    
    Args:
        hex_string: 32-character hex string
    
    Returns:
        OTel trace_id as int64
    """
    if not hex_string:
        return 0
    return int(hex_string, 16)


def parse_span_id(hex_string: str) -> int:
    """
    Parse hex string span_id to OTel int64.
    
    Args:
        hex_string: 16-character hex string
    
    Returns:
        OTel span_id as int64
    """
    if not hex_string:
        return 0
    return int(hex_string, 16)
