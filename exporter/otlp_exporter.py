"""OTLP exporter using OpenTelemetry OTLP HTTP exporter."""

from __future__ import annotations

from typing import Iterable, Optional, Any

from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as OTelOTLPSpanExporter
from opentelemetry.sdk.trace.export import SpanExporter as OTelSpanExporter, SpanExportResult


class OTLPExporter:
    """
    OTLP exporter wrapper that maintains Traccia exporter interface.
    
    This wraps OpenTelemetry's OTLP HTTP exporter to work with Traccia's
    BatchSpanProcessor which expects an `export()` method.
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 10.0,
        headers: Optional[dict] = None,
    ) -> None:
        """
        Initialize OTLP exporter.
        
        Args:
            endpoint: OTLP endpoint URL (defaults to OTel default)
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds
            headers: Optional additional headers
        """
        # Build headers
        export_headers = dict(headers) if headers else {}
        if api_key:
            export_headers["Authorization"] = f"Bearer {api_key}"
        
        # Create OTel OTLP exporter
        self._otel_exporter = OTelOTLPSpanExporter(
            endpoint=endpoint,
            timeout=timeout,
            headers=export_headers if export_headers else None,
        )
        
        self.endpoint = endpoint
        self.api_key = api_key
        self.timeout = timeout

    def export(self, spans: Iterable[Any]) -> bool:
        """
        Export spans using OTLP format.
        
        Args:
            spans: Iterable of Traccia-compatible spans
        
        Returns:
            True if export succeeded, False otherwise
        """
        spans_list = list(spans)
        if not spans_list:
            return True
        
        # Convert Traccia spans to OTel ReadableSpan format
        from opentelemetry.sdk.trace.export import ReadableSpan
        from opentelemetry.trace import SpanContext, TraceFlags, TraceState
        from opentelemetry.sdk.trace import Resource
        from opentelemetry.trace import Status, StatusCode
        
        from traccia.utils.helpers import parse_trace_id, parse_span_id
        
        readable_spans = []
        
        for span in spans_list:
            # Get OTel span from Traccia wrapper
            # Traccia Span wraps OTel Span
            otel_span = None
            
            if hasattr(span, '_otel_span'):
                otel_span = span._otel_span
            elif isinstance(span, ReadableSpan):
                # Already a ReadableSpan (from OTel SDK directly)
                readable_spans.append(span)
                continue
            else:
                # Try to use span directly if it's OTel-compatible
                otel_span = span
            
            # Check if it's already a ReadableSpan (OTel SDK provides this when span ends)
            if isinstance(otel_span, ReadableSpan):
                readable_spans.append(otel_span)
                continue
            
            # Try to get ReadableSpan from OTel span if it's ended
            # OTel SDK stores ReadableSpan in the span's internal state when it ends
            if hasattr(otel_span, '_readable_span'):
                readable_spans.append(otel_span._readable_span)
                continue
            
            # If OTel span is from SDK, try to get it from the span processor
            # OTel SDK's BatchSpanProcessor receives ReadableSpan in on_end()
            # But we're using our own processor, so we need to convert manually
            
            # Fallback: convert Traccia span to ReadableSpan manually
            # This handles Traccia Span that wraps an active OTel Span
            try:
                # Parse trace/span IDs
                trace_id = parse_trace_id(span.context.trace_id)
                span_id = parse_span_id(span.context.span_id)
                
                # Create OTel SpanContext
                trace_flags = TraceFlags(span.context.trace_flags)
                trace_state = TraceState()
                if span.context.trace_state:
                    from traccia.context.propagators import parse_tracestate
                    parsed = parse_tracestate(span.context.trace_state)
                    if parsed:
                        items = [(k, v) for k, v in parsed.items()]
                        trace_state = TraceState(items)
                
                otel_context = SpanContext(
                    trace_id=trace_id,
                    span_id=span_id,
                    is_remote=False,
                    trace_flags=trace_flags,
                    trace_state=trace_state,
                )
                
                # Convert status
                if span.status.value == 1:  # OK
                    otel_status = Status(status_code=StatusCode.OK, description=span.status_description)
                elif span.status.value == 2:  # ERROR
                    otel_status = Status(status_code=StatusCode.ERROR, description=span.status_description)
                else:
                    otel_status = Status(status_code=StatusCode.UNSET, description=span.status_description)
                
                # Convert events
                otel_events = []
                if span.events:
                    from opentelemetry.sdk.trace import Event
                    for ev in span.events:
                        otel_events.append(Event(
                            name=ev.get("name", ""),
                            timestamp=ev.get("timestamp_ns", span.start_time_ns),
                            attributes=ev.get("attributes", {}),
                        ))
                
                # Get resource
                resource = Resource.create({})
                if hasattr(span, 'tracer') and span.tracer:
                    provider = getattr(span.tracer, '_provider', None)
                    if provider:
                        resource = provider._otel_provider.resource
                
                # Create ReadableSpan
                readable_span = ReadableSpan(
                    name=span.name,
                    context=otel_context,
                    parent=parse_span_id(span.parent_span_id) if span.parent_span_id else None,
                    kind=None,  # Not available in Traccia
                    start_time=span.start_time_ns,
                    end_time=span.end_time_ns,
                    status=otel_status,
                    attributes=span.attributes,
                    events=otel_events,
                    links=[],
                    resource=resource,
                    instrumentation_scope=None,  # Will be set by OTel
                )
                readable_spans.append(readable_span)
            except Exception:
                # If conversion fails, skip this span
                continue
        
        if not readable_spans:
            return True
        
        # Export using OTel exporter
        result = self._otel_exporter.export(readable_spans)
        return result == SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        """Shutdown the exporter."""
        self._otel_exporter.shutdown()

    def force_flush(self, timeout_millis: Optional[int] = None) -> None:
        """Force flush any pending spans."""
        timeout = timeout_millis / 1000.0 if timeout_millis else None
        self._otel_exporter.force_flush(timeout_millis=int(timeout * 1000) if timeout else 30000)
