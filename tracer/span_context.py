"""Immutable trace metadata."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SpanContext:
    trace_id: str
    span_id: str
    trace_flags: int = 1  # 1 = sampled, 0 = not sampled
    trace_state: Optional[str] = None

    def is_valid(self) -> bool:
        return bool(self.trace_id and self.span_id)

