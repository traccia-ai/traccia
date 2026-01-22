"""Anthropic monkey patching for messages.create."""

from __future__ import annotations

from typing import Any, Dict, Optional
from traccia.tracer.span import SpanStatus

_patched = False


def _safe_get(obj, path: str, default=None):
    cur = obj
    for part in path.split("."):
        if cur is None:
            return default
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = getattr(cur, part, None)
    return cur if cur is not None else default


def patch_anthropic() -> bool:
    """Patch Anthropic messages.create; returns True if patched, False otherwise."""
    global _patched
    if _patched:
        return True
    try:
        import anthropic
    except Exception:
        return False

    client_cls = getattr(anthropic, "Anthropic", None)
    if client_cls is None:
        return False

    original = getattr(client_cls, "messages", None)
    if original is None:
        return False

    create_fn = getattr(original, "create", None)
    if create_fn is None:
        return False
    if getattr(create_fn, "_agent_trace_patched", False):
        _patched = True
        return True

    def wrapped_create(self, *args, **kwargs):
        tracer = _get_tracer("anthropic")
        model = kwargs.get("model") or _safe_get(args, "0.model", None)
        attributes: Dict[str, Any] = {"llm.vendor": "anthropic"}
        if model:
            attributes["llm.model"] = model
        with tracer.start_as_current_span("llm.anthropic.messages", attributes=attributes) as span:
            try:
                resp = create_fn(self, *args, **kwargs)
                usage = getattr(resp, "usage", None) or resp.get("usage") if isinstance(resp, dict) else None
                if usage:
                    span.set_attribute("llm.usage.source", "provider_usage")
                    for k in ("input_tokens", "output_tokens"):
                        if k in usage:
                            span.set_attribute(f"llm.usage.{k}", usage[k])
                    # Provide OpenAI-style aliases so downstream processors (cost, etc.)
                    # can treat Anthropic uniformly.
                    if "input_tokens" in usage and "llm.usage.prompt_tokens" not in span.attributes:
                        span.set_attribute("llm.usage.prompt_tokens", usage["input_tokens"])
                    if "input_tokens" in usage:
                        span.set_attribute("llm.usage.prompt_source", "provider_usage")
                    if "output_tokens" in usage and "llm.usage.completion_tokens" not in span.attributes:
                        span.set_attribute("llm.usage.completion_tokens", usage["output_tokens"])
                    if "output_tokens" in usage:
                        span.set_attribute("llm.usage.completion_source", "provider_usage")
                stop_reason = _safe_get(resp, "stop_reason") or _safe_get(resp, "stop_reason", None)
                if stop_reason:
                    span.set_attribute("llm.stop_reason", stop_reason)
                return resp
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(SpanStatus.ERROR, str(exc))
                raise

    wrapped_create._agent_trace_patched = True
    setattr(original, "create", wrapped_create)
    _patched = True
    return True


def _get_tracer(name: str):
    import traccia

    return traccia.get_tracer(name)

