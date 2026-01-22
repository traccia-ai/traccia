"""Queue overflow handling strategies for span buffering."""

from collections import deque
from typing import Deque

from traccia.tracer.span import Span


class DropPolicy:
    """Base policy deciding how to handle span queue overflow."""

    def handle(self, queue: Deque[Span], span: Span, max_size: int) -> bool:
        """
        Apply the drop policy.

        Returns True if the span was enqueued, False if it was dropped.
        """
        raise NotImplementedError


class DropOldestPolicy(DropPolicy):
    """Drop the oldest span to make room for a new one."""

    def handle(self, queue: Deque[Span], span: Span, max_size: int) -> bool:
        if len(queue) >= max_size and queue:
            queue.popleft()
        if len(queue) < max_size:
            queue.append(span)
            return True
        return False


class DropNewestPolicy(DropPolicy):
    """Drop the incoming span if the queue is full."""

    def handle(self, queue: Deque[Span], span: Span, max_size: int) -> bool:
        if len(queue) < max_size:
            queue.append(span)
            return True
        return False


DEFAULT_DROP_POLICY = DropOldestPolicy()

