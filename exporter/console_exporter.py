"""Console exporter for developer visibility."""

from __future__ import annotations

import sys
from typing import Iterable

from traccia.tracer.span import Span


class ConsoleExporter:
    """Simple exporter that prints spans to stdout (or provided stream)."""

    def __init__(self, stream=None) -> None:
        self.stream = stream or sys.stdout

    def export(self, spans: Iterable[Span]) -> bool:
        for span in spans:
            line = (
                f"[span] name={span.name} trace_id={span.context.trace_id} "
                f"span_id={span.context.span_id} status={span.status.name} "
                f"duration_ns={span.duration_ns}"
            )
            if span.attributes:
                line += f" attrs={span.attributes}"
            print(line, file=self.stream)
        return True

    def shutdown(self) -> None:
        return None

