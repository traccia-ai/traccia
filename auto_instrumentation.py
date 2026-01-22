"""Optional auto-instrumentation for user-provided tool functions.

The SDK supports explicit instrumentation via the `@observe` decorator. This
module provides a best-effort utility for wrapping existing callables by dotted
path strings.

Accepted include formats:
- "package.module:function"
- "package.module.function"

This is intentionally conservative: it mainly targets module-level functions.
If a target can't be resolved or isn't callable, it's skipped.
"""

from __future__ import annotations

import importlib
from typing import Iterable, Optional, Tuple

from traccia.instrumentation.decorator import observe
from traccia import runtime_config


def _split_target(spec: str) -> Optional[Tuple[str, str]]:
    if not spec:
        return None
    if ":" in spec:
        mod, attr = spec.split(":", 1)
        return mod.strip(), attr.strip()
    # Heuristic: last segment is the attribute name; rest is module
    if "." not in spec:
        return None
    mod, attr = spec.rsplit(".", 1)
    return mod.strip(), attr.strip()


def instrument_functions(include: Iterable[str]) -> None:
    """
    Wrap and replace functions referenced by include specs.

    This is best-effort and will silently skip invalid entries.
    """
    if not runtime_config.get_auto_instrument_tools():
        return

    for spec in include or []:
        parsed = _split_target(str(spec))
        if not parsed:
            continue
        module_name, attr_name = parsed
        try:
            mod = importlib.import_module(module_name)
        except Exception:
            continue

        try:
            target = getattr(mod, attr_name)
        except Exception:
            continue
        if not callable(target):
            continue

        # Avoid double wrapping
        if getattr(target, "_agent_trace_observed", False):
            continue

        wrapped = observe(name=f"{module_name}.{attr_name}", as_type="tool")(target)
        setattr(wrapped, "_agent_trace_observed", True)
        try:
            setattr(mod, attr_name, wrapped)
        except Exception:
            continue


