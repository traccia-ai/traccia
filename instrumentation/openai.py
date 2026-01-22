"""OpenAI monkey patching for chat completions."""

from __future__ import annotations

from typing import Any, Dict, Optional, Callable
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


def patch_openai() -> bool:
    """Patch OpenAI chat completions for both legacy and new client APIs."""
    global _patched
    if _patched:
        return True
    try:
        import openai
    except Exception:
        return False

    def _extract_messages(kwargs, args):
        messages = kwargs.get("messages")
        # For new client, first arg after self is messages
        if messages is None and len(args) >= 2:
            messages = args[1]
        if not messages or not isinstance(messages, (list, tuple)):
            return None
        # Keep only JSON-friendly, small fields to avoid huge/sensitive payloads.
        slim = []
        for m in list(messages)[:50]:
            if not isinstance(m, dict):
                continue
            role = m.get("role")
            name = m.get("name")
            content = m.get("content")
            if isinstance(content, (list, dict)):
                content = str(content)
            elif content is not None and not isinstance(content, str):
                content = str(content)
            item = {"role": role, "content": content}
            if name:
                item["name"] = name
            slim.append(item)
        return slim or None

    def _extract_prompt_text(messages_slim) -> Optional[str]:
        if not messages_slim:
            return None
        parts = []
        for m in messages_slim:
            role = m.get("role")
            content = m.get("content")
            if not content:
                continue
            parts.append(f"{role}: {content}" if role else str(content))
        return "\n".join(parts) if parts else None

    def _extract_prompt(kwargs, args) -> Optional[str]:
        messages = kwargs.get("messages")
        if messages is None and len(args) >= 2:
            messages = args[1]
        if not messages:
            return None
        parts = []
        for m in messages:
            content = m.get("content")
            role = m.get("role")
            if content:
                parts.append(f"{role}: {content}" if role else str(content))
        return "\n".join(parts) if parts else None

    def _wrap(create_fn: Callable):
        if getattr(create_fn, "_agent_trace_patched", False):
            return create_fn

        def wrapped_create(*args, **kwargs):
            tracer = _get_tracer("openai")
            model = kwargs.get("model") or _safe_get(args, "0.model", None)
            messages_slim = _extract_messages(kwargs, args)
            prompt_text = _extract_prompt_text(messages_slim) or _extract_prompt(kwargs, args)
            attributes: Dict[str, Any] = {"llm.vendor": "openai"}
            if model:
                attributes["llm.model"] = model
            if messages_slim:
                # Convert messages to JSON string for OTel compatibility
                import json
                try:
                    attributes["llm.openai.messages"] = json.dumps(messages_slim)[:1000]
                except Exception:
                    attributes["llm.openai.messages"] = str(messages_slim)[:1000]
            if prompt_text:
                attributes["llm.prompt"] = prompt_text
            with tracer.start_as_current_span("llm.openai.chat.completions", attributes=attributes) as span:
                try:
                    resp = create_fn(*args, **kwargs)
                    # capture model from response if not already set
                    resp_model = getattr(resp, "model", None) or (_safe_get(resp, "model"))
                    if resp_model and "llm.model" not in span.attributes:
                        span.set_attribute("llm.model", resp_model)
                    usage = getattr(resp, "usage", None) or (resp.get("usage") if isinstance(resp, dict) else None)
                    if usage:
                        span.set_attribute("llm.usage.source", "provider_usage")
                        for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
                            val = getattr(usage, k, None) if not isinstance(usage, dict) else usage.get(k)
                            if val is not None:
                                span.set_attribute(f"llm.usage.{k}", val)
                        if "llm.usage.prompt_tokens" in span.attributes:
                            span.set_attribute("llm.usage.prompt_source", "provider_usage")
                        if "llm.usage.completion_tokens" in span.attributes:
                            span.set_attribute("llm.usage.completion_source", "provider_usage")
                    finish_reason = _safe_get(resp, "choices.0.finish_reason")
                    if finish_reason:
                        span.set_attribute("llm.finish_reason", finish_reason)
                    completion = _safe_get(resp, "choices.0.message.content")
                    if completion:
                        span.set_attribute("llm.completion", completion)
                    return resp
                except Exception as exc:
                    span.record_exception(exc)
                    span.set_status(SpanStatus.ERROR, str(exc))
                    raise

        wrapped_create._agent_trace_patched = True
        return wrapped_create

    patched_any = False

    # Legacy: openai.ChatCompletion.create
    target_legacy = getattr(openai, "ChatCompletion", None) or getattr(openai, "chat", None)
    if target_legacy:
        create_fn = getattr(target_legacy, "create", None)
        if create_fn:
            setattr(target_legacy, "create", _wrap(create_fn))
            patched_any = True

    # New client: OpenAI.chat.completions.create
    new_client_cls = getattr(openai, "OpenAI", None)
    if new_client_cls and hasattr(new_client_cls, "chat"):
        chat = getattr(new_client_cls, "chat", None)
        if chat and hasattr(chat, "completions"):
            completions = getattr(chat, "completions")
            if hasattr(completions, "create"):
                patched = _wrap(completions.create)
                setattr(completions, "create", patched)
                patched_any = True

    # New client resource class: openai.resources.chat.completions.Completions
    try:
        from openai.resources.chat.completions import Completions  # type: ignore

        if hasattr(Completions, "create"):
            Completions.create = _wrap(Completions.create)
            patched_any = True
    except Exception:
        pass

    if patched_any:
        _patched = True
    return patched_any


def _get_tracer(name: str):
    import traccia

    return traccia.get_tracer(name)

