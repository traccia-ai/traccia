"""Batching span processor with bounded queue and background flush."""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Deque, Iterable, List, Optional

from traccia.processors.drop_policy import DEFAULT_DROP_POLICY, DropPolicy
from traccia.processors.sampler import Sampler
from traccia.tracer.provider import SpanProcessor
from traccia.tracer.span import Span


class BatchSpanProcessor(SpanProcessor):
    """
    Batch span processor that queues spans for export.
    
    Note: This runs as an enrichment processor (before span.end()),
    but it queues spans and exports them after they end.
    When exporting, it extracts ReadableSpan from the OTel span.
    """
    
    def __init__(
        self,
        exporter=None,
        *,
        max_queue_size: int = 5000,
        max_export_batch_size: int = 512,
        schedule_delay_millis: int = 5000,
        drop_policy: Optional[DropPolicy] = None,
        sampler: Optional[Sampler] = None,
    ) -> None:
        self.exporter = exporter
        self.max_queue_size = max_queue_size
        self.max_export_batch_size = max_export_batch_size
        self.schedule_delay = schedule_delay_millis / 1000.0
        self.drop_policy = drop_policy or DEFAULT_DROP_POLICY
        self.sampler = sampler

        self._queue: Deque[Span] = deque()
        self._lock = threading.Lock()
        self._event = threading.Event()
        self._shutdown = False
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

    def on_end(self, span: Span) -> None:
        """
        Called when a span ends (BEFORE span.end() is called).
        
        We queue the span here, but it hasn't ended yet.
        The span will end after enrichment processors run.
        
        Note: We mark the span as queued to prevent double-queuing.
        """
        if self._shutdown:
            return

        # Head-based sampling is recorded on SpanContext.trace_flags.
        # If a sampler is configured, traces marked as not-sampled (0) are dropped.
        if self.sampler and getattr(span.context, "trace_flags", 1) == 0:
            return

        # Prevent double-queuing (span might be queued multiple times if on_end is called multiple times)
        if hasattr(span, '_batch_queued') and span._batch_queued:
            return

        with self._lock:
            enqueued = self.drop_policy.handle(self._queue, span, self.max_queue_size)
            if enqueued:
                span._batch_queued = True  # Mark as queued
                self._event.set()

    def force_flush(self, timeout: Optional[float] = None) -> None:
        """Force flush any pending spans."""
        deadline = time.time() + timeout if timeout else None
        while True:
            flushed_any = self._flush_once()
            if not flushed_any:
                return
            if deadline and time.time() >= deadline:
                return

    def shutdown(self) -> None:
        """Shutdown the processor."""
        self._shutdown = True
        self._event.set()
        self._worker.join(timeout=self.schedule_delay * 2)
        self.force_flush()

    # Internal
    def _worker_loop(self) -> None:
        """Background worker that periodically flushes spans."""
        while not self._shutdown:
            self._event.wait(timeout=self.schedule_delay)
            self._event.clear()
            self._flush_once()

    def _flush_once(self) -> bool:
        """Flush one batch of spans."""
        spans = self._drain_queue(self.max_export_batch_size)
        if not spans:
            return False
        self._export(spans)
        return True

    def _drain_queue(self, limit: int) -> List[Span]:
        """Drain spans from queue up to limit."""
        items: List[Span] = []
        with self._lock:
            while self._queue and len(items) < limit:
                items.append(self._queue.popleft())
        return items

    def _export(self, spans: Iterable[Span]) -> None:
        """
        Export spans to exporter.
        
        Spans should be ended by the time they're flushed from the queue.
        We filter out any spans that aren't ended yet.
        """
        if self.exporter is None:
            return
        
        try:
            # Filter to only ended spans
            ended_spans = [span for span in spans if span._ended]
            
            if not ended_spans:
                return
            
            # Export spans - exporter will handle conversion if needed
            self.exporter.export(ended_spans)
        except Exception as e:
            # Export errors are swallowed; resilience over strictness.
            import traceback
            traceback.print_exc()
            return
