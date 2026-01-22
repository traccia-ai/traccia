"""Span processor that annotates spans with cost based on token usage and pricing."""

from __future__ import annotations

from typing import Dict, Optional

from traccia.processors.cost_engine import compute_cost, match_pricing_model_key
from traccia.tracer.provider import SpanProcessor


class CostAnnotatingProcessor(SpanProcessor):
    """
    Adds `llm.cost.usd` to spans when token usage and model info are available.

    Expects spans to carry:
      - llm.model (model name)
      - llm.usage.prompt_tokens
      - llm.usage.completion_tokens
    """

    def __init__(
        self,
        pricing_table: Optional[Dict[str, Dict[str, float]]] = None,
        *,
        pricing_source: str = "default",
    ) -> None:
        self.pricing_table = pricing_table or {}
        self.pricing_source = pricing_source

    def on_end(self, span) -> None:
        if "llm.cost.usd" in (span.attributes or {}):
            return
        model = span.attributes.get("llm.model")
        prompt = span.attributes.get("llm.usage.prompt_tokens")
        completion = span.attributes.get("llm.usage.completion_tokens")
        # Anthropic-style names (also supported)
        if prompt is None:
            prompt = span.attributes.get("llm.usage.input_tokens")
        if completion is None:
            completion = span.attributes.get("llm.usage.output_tokens")
        if not model or prompt is None or completion is None:
            return
        cost = compute_cost(
            model,
            int(prompt),
            int(completion),
            pricing_table=self.pricing_table,
        )
        if cost is not None:
            span.set_attribute("llm.cost.usd", cost)
            # Provenance for downstream analysis.
            span.set_attribute("llm.cost.source", span.attributes.get("llm.usage.source", "unknown"))
            span.set_attribute("llm.pricing.source", self.pricing_source)
            key = match_pricing_model_key(model, self.pricing_table)
            if key:
                span.set_attribute("llm.pricing.model_key", key)

    def shutdown(self) -> None:
        return None

    def force_flush(self, timeout: Optional[float] = None) -> None:
        return None

    def update_pricing_table(
        self, pricing_table: Dict[str, Dict[str, float]], pricing_source: Optional[str] = None
    ) -> None:
        self.pricing_table = pricing_table
        if pricing_source:
            self.pricing_source = pricing_source

