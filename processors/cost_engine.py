"""Cost calculation based on model pricing and token usage."""

from __future__ import annotations

from typing import Dict, Optional, Tuple

DEFAULT_PRICING: Dict[str, Dict[str, float]] = {
    # prices per 1k tokens
    "gpt-4": {"prompt": 0.03, "completion": 0.06},
    "gpt-4o": {"prompt": 0.005, "completion": 0.015},
    "gpt-3.5-turbo": {"prompt": 0.0015, "completion": 0.002},
    "claude-3-opus": {"prompt": 0.015, "completion": 0.075},
    "claude-3-sonnet": {"prompt": 0.003, "completion": 0.015},
    # Add other models via pricing overrides:
    #   - env: AGENT_DASHBOARD_PRICING_JSON='{"model": {"prompt": x, "completion": y}}'
    #   - start_tracing(pricing_override={...})
}

def _lookup_price(model: str, table: Dict[str, Dict[str, float]]) -> Optional[Tuple[str, Dict[str, float]]]:
    """
    Return (matched_key, price_dict) for a given model name.

    Supports exact matches and prefix matches for version-suffixed model names:
    e.g. "claude-3-opus-20240229" -> "claude-3-opus"
         "gpt-4o-2024-08-06" -> "gpt-4o"
    """
    if not model:
        return None
    m = str(model).strip()
    if not m:
        return None
    # exact (case sensitive + lower)
    if m in table:
        return m, table[m]
    ml = m.lower()
    if ml in table:
        return ml, table[ml]
    # prefix match (longest key wins)
    for key in sorted(table.keys(), key=len, reverse=True):
        if ml.startswith(key.lower()):
            return key, table[key]
    return None


def match_pricing_model_key(
    model: str, pricing_table: Optional[Dict[str, Dict[str, float]]] = None
) -> Optional[str]:
    """Return the pricing table key that would be used for `model`, if any."""
    table = pricing_table or DEFAULT_PRICING
    matched = _lookup_price(model, table)
    if not matched:
        return None
    key, _ = matched
    return key


def compute_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    pricing_table: Optional[Dict[str, Dict[str, float]]] = None,
) -> Optional[float]:
    table = pricing_table or DEFAULT_PRICING
    matched = _lookup_price(model, table)
    if not matched:
        return None
    _, price = matched
    prompt_cost = (prompt_tokens / 1000.0) * price.get("prompt", 0.0)
    completion_cost = (completion_tokens / 1000.0) * price.get("completion", 0.0)
    return round(prompt_cost + completion_cost, 6)

