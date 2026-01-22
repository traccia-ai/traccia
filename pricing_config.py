"""Pricing configuration fetcher with optional env override.

Pricing should be treated as configuration, not source code: vendors update
prices and model versions frequently. The SDK therefore supports:
- defaults (stub)
- env override: AGENT_DASHBOARD_PRICING_JSON
- direct override via start_tracing(pricing_override=...)
"""

from __future__ import annotations

import json
import os
from typing import Dict, Literal, Tuple

from traccia.processors.cost_engine import DEFAULT_PRICING


def fetch_remote_pricing() -> Dict[str, Dict[str, float]]:
    """
    Placeholder for remote pricing sync.
    In production this would fetch from backend service; here we return defaults.
    """
    return DEFAULT_PRICING.copy()


PricingSource = Literal["default", "env", "override"]


def load_pricing_with_source(
    override: Dict[str, Dict[str, float]] | None = None,
) -> Tuple[Dict[str, Dict[str, float]], PricingSource]:
    """
    Return (pricing_table, source_of_latest_override).
    """
    pricing = fetch_remote_pricing()
    source: PricingSource = "default"

    env_override = os.getenv("AGENT_DASHBOARD_PRICING_JSON")
    if env_override:
        try:
            env_pricing = json.loads(env_override)
            if isinstance(env_pricing, dict):
                pricing.update(env_pricing)
                source = "env"
        except Exception:
            pass
    if override:
        pricing.update(override)
        source = "override"
    return pricing, source


def load_pricing(override: Dict[str, Dict[str, float]] | None = None) -> Dict[str, Dict[str, float]]:
    """Backward-compatible helper returning only the pricing table."""
    pricing, _ = load_pricing_with_source(override)
    return pricing

