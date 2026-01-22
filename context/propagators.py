"""W3C trace context propagation using OpenTelemetry's standard propagators."""

from __future__ import annotations

from typing import Dict, Optional, Any

from opentelemetry.propagate import inject as otel_inject, extract as otel_extract
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.trace import get_current_span, set_span_in_context
from opentelemetry.trace import SpanContext as OTelSpanContext, TraceFlags, TraceState
from opentelemetry.trace import NonRecordingSpan
from opentelemetry import context as context_api

from traccia.tracer.span_context import SpanContext
from traccia.utils.helpers import format_trace_id, format_span_id, parse_trace_id, parse_span_id

# Use OTel's W3C Trace Context propagator
_propagator = TraceContextTextMapPropagator()


def format_traceparent(context: SpanContext) -> str:
    """
    Format traceparent header value (W3C Trace Context standard).
    
    Uses OpenTelemetry's propagator internally.
    """
    # Convert Traccia SpanContext to OTel SpanContext
    otel_context = _traccia_to_otel_context(context)
    
    # Create a non-recording span with the context
    span = NonRecordingSpan(otel_context)
    ctx = set_span_in_context(span)
    
    # Create a carrier dict and inject
    carrier: Dict[str, str] = {}
    _propagator.inject(carrier, context=ctx)
    
    # Extract traceparent from carrier
    return carrier.get("traceparent", "")


def format_tracestate(state: Dict[str, str]) -> str:
    """
    Format tracestate header value from a dict.
    
    Formats according to W3C Trace Context standard.
    """
    if not state:
        return ""
    
    # Format manually (W3C format: key1=value1,key2=value2)
    items = []
    for k, v in state.items():
        # Sanitize key and value
        key = str(k).strip().lower()[:256]
        value = str(v).strip().replace(",", "_").replace("=", "_")[:256]
        if key and value:
            items.append(f"{key}={value}")
    
    return ",".join(items)


def parse_tracestate(header_value: str) -> Dict[str, str]:
    """
    Parse a tracestate header into a dict.
    
    Parses W3C Trace Context tracestate format: key1=value1,key2=value2
    """
    if not header_value:
        return {}
    
    result = {}
    for item in header_value.split(","):
        item = item.strip()
        if not item or "=" not in item:
            continue
        parts = item.split("=", 1)
        if len(parts) == 2:
            key = parts[0].strip().lower()
            value = parts[1].strip()
            if key and value:
                result[key] = value
    
    return result


def parse_traceparent(header_value: str) -> Optional[SpanContext]:
    """
    Parse a traceparent header into a SpanContext.
    
    Uses OpenTelemetry's W3C Trace Context parser.
    """
    if not header_value:
        return None
    
    # Use OTel to parse traceparent
    carrier = {"traceparent": header_value}
    ctx = _propagator.extract(carrier)
    
    # Get span context from OTel context
    span = get_current_span(context=ctx)
    if span:
        otel_context = span.get_span_context()
        if otel_context.is_valid:
            return _otel_to_traccia_context(otel_context)
    
    return None


def inject_traceparent(headers: Dict[str, str], context: SpanContext) -> None:
    """
    Inject traceparent header into headers dict.
    
    Uses OpenTelemetry's inject() function.
    """
    # Convert Traccia context to OTel context
    otel_context = _traccia_to_otel_context(context)
    
    # Create OTel context with span
    span = NonRecordingSpan(otel_context)
    ctx = set_span_in_context(span)
    
    # Inject using OTel
    _propagator.inject(carrier=headers, context=ctx)


def inject_tracestate(headers: Dict[str, str], context: SpanContext) -> None:
    """
    Inject tracestate header if present on the context.
    
    Uses OpenTelemetry's inject() function.
    """
    if not context.trace_state:
        return
    
    # Parse tracestate and create OTel TraceState
    parsed = parse_tracestate(context.trace_state)
    if parsed:
        trace_state = TraceState([(k, v) for k, v in parsed.items()])
        
        # Convert Traccia context to OTel context with tracestate
        otel_context = _traccia_to_otel_context(context)
        # Update trace_state
        otel_context = OTelSpanContext(
            trace_id=otel_context.trace_id,
            span_id=otel_context.span_id,
            is_remote=otel_context.is_remote,
            trace_flags=otel_context.trace_flags,
            trace_state=trace_state,
        )
        
        # Create span with context and inject
        span = NonRecordingSpan(otel_context)
        ctx = set_span_in_context(span)
        _propagator.inject(carrier=headers, context=ctx)


def extract_traceparent(headers: Dict[str, str]) -> Optional[SpanContext]:
    """
    Extract traceparent header from headers and parse it.
    
    Uses OpenTelemetry's extract() function.
    """
    # Use OTel to extract
    ctx = _propagator.extract(carrier=headers)
    
    # Get span from context
    span = get_current_span(context=ctx)
    if span:
        otel_context = span.get_span_context()
        if otel_context.is_valid:
            return _otel_to_traccia_context(otel_context)
    
    return None


def extract_tracestate(headers: Dict[str, str]) -> Optional[str]:
    """
    Extract tracestate header value (case-insensitive).
    
    Returns the raw tracestate string.
    """
    # Case-insensitive lookup
    for key, value in headers.items():
        if key.lower() == "tracestate":
            return value
    return None


def extract_trace_context(headers: Dict[str, str]) -> Optional[SpanContext]:
    """
    Extract both traceparent and tracestate and return a combined SpanContext.
    
    Uses OpenTelemetry's extract() function.
    """
    # Use OTel to extract both
    ctx = _propagator.extract(carrier=headers)
    
    # Get span from context
    span = get_current_span(context=ctx)
    if span:
        otel_context = span.get_span_context()
        if otel_context.is_valid:
            # Extract tracestate separately
            tracestate_str = extract_tracestate(headers)
            return _otel_to_traccia_context(otel_context, tracestate_str)
    
    return None


# Helper functions for context conversion

def _traccia_to_otel_context(traccia_context: SpanContext) -> OTelSpanContext:
    """Convert Traccia SpanContext to OTel SpanContext."""
    trace_id = parse_trace_id(traccia_context.trace_id)
    span_id = parse_span_id(traccia_context.span_id)
    trace_flags = TraceFlags(traccia_context.trace_flags)
    
    # Parse trace_state
    trace_state = TraceState()
    if traccia_context.trace_state:
        parsed = parse_tracestate(traccia_context.trace_state)
        if parsed:
            items = [(k, v) for k, v in parsed.items()]
            trace_state = TraceState(items)
    
    return OTelSpanContext(
        trace_id=trace_id,
        span_id=span_id,
        is_remote=False,
        trace_flags=trace_flags,
        trace_state=trace_state,
    )


def _otel_to_traccia_context(otel_context: OTelSpanContext, tracestate_str: Optional[str] = None) -> SpanContext:
    """Convert OTel SpanContext to Traccia SpanContext."""
    trace_id = format_trace_id(otel_context.trace_id)
    span_id = format_span_id(otel_context.span_id)
    trace_flags = 1 if otel_context.trace_flags.sampled else 0
    
    # Format trace_state
    trace_state = None
    if tracestate_str:
        trace_state = tracestate_str
    elif otel_context.trace_state:
        # Format OTel TraceState to string
        items = []
        for key, value in otel_context.trace_state.items():
            items.append(f"{key}={value}")
        if items:
            trace_state = ",".join(items)
    
    return SpanContext(
        trace_id=trace_id,
        span_id=span_id,
        trace_flags=trace_flags,
        trace_state=trace_state,
    )


# Additional helper: inject/extract using OTel's standard API

def inject(carrier: Dict[str, str], context: Optional[Any] = None) -> None:
    """
    Inject trace context into carrier using OpenTelemetry's standard API.
    
    This is a convenience function that uses OTel's inject() directly.
    If context is not provided, uses current context.
    """
    if context is None:
        otel_inject(carrier)
    else:
        otel_inject(carrier, context=context)


def extract(carrier: Dict[str, str]) -> Any:
    """
    Extract trace context from carrier using OpenTelemetry's standard API.
    
    Returns OTel context that can be used with start_span().
    """
    return otel_extract(carrier)
