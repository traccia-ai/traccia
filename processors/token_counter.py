"""Token counting utilities and processor for spans with LLM usage.

Best practice:
- Prefer provider-reported usage tokens when available.
- Otherwise, estimate with the vendor tokenizer when available (tiktoken for
  OpenAI) and record the estimate source on the span.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from traccia.tracer.provider import SpanProcessor

try:  # optional dependency for accurate counting
    import tiktoken  # type: ignore
except Exception:  # pragma: no cover
    tiktoken = None  # fallback to heuristic


MODEL_TO_ENCODING = {
    # OpenAI mappings (approximate; kept current as of gpt-4o family)
    "gpt-4o": "o200k_base",
    "gpt-4o-mini": "o200k_base",
    "gpt-4": "cl100k_base",
    "gpt-3.5-turbo": "cl100k_base",
}


def _encoding_for_model(model: Optional[str]):
    if tiktoken is None:
        return None
    if not model:
        return None
    m = str(model)
    # First try tiktoken's model registry (best when available).
    try:
        return tiktoken.encoding_for_model(m)
    except Exception:
        pass
    # Then try our explicit mapping, supporting version-suffixed models by prefix.
    encoding_name = MODEL_TO_ENCODING.get(m)
    if encoding_name is None:
        for key in sorted(MODEL_TO_ENCODING.keys(), key=len, reverse=True):
            if m.startswith(key):
                encoding_name = MODEL_TO_ENCODING[key]
                break
    if encoding_name:
        try:
            return tiktoken.get_encoding(encoding_name)
        except Exception:
            return None
    return None


def _count_with_tiktoken(text: str, model: Optional[str]) -> Optional[int]:
    if tiktoken is None or not text:
        return None
    encoding = _encoding_for_model(model)
    if encoding is None:
        return None
    try:
        return len(encoding.encode(text))
    except Exception:
        return None


def estimate_tokens_from_text(text: str, model: Optional[str] = None) -> int:
    """
    Estimate tokens. Prefer model-accurate count via tiktoken when available,
    otherwise fall back to a rough whitespace split.
    """
    if not text:
        return 0
    exact = _count_with_tiktoken(text, model)
    if exact is not None:
        return exact
    return len(text.split())


def estimate_tokens_from_text_with_source(
    text: str, model: Optional[str] = None
) -> Tuple[int, str]:
    """
    Return (token_count, source) where source is:
      - "estimated.tiktoken"
      - "estimated.heuristic"
    """
    if not text:
        return 0, "estimated.heuristic"
    exact = _count_with_tiktoken(text, model)
    if exact is not None:
        return exact, "estimated.tiktoken"
    return len(text.split()), "estimated.heuristic"


def _openai_chat_overhead(model: Optional[str]) -> Tuple[int, int, int]:
    """
    Return (tokens_per_message, tokens_per_name, tokens_for_reply).

    These constants are model-dependent in OpenAI's chat format. For estimation
    we use a reasonable default that is close for many modern chat models.
    """
    # Defaults (works reasonably for gpt-4/4o families as an estimate)
    return 3, 1, 3


def estimate_openai_chat_prompt_tokens_with_source(
    messages: Any, model: Optional[str] = None
) -> Optional[Tuple[int, str]]:
    """
    Estimate prompt tokens from a list of chat messages.

    This is best-effort and should be treated as an estimate unless provider
    usage is available.
    """
    if not isinstance(messages, (list, tuple)) or not messages:
        return None
    if tiktoken is None:
        # Heuristic fallback: count whitespace tokens across role/content.
        parts = []
        for msg in list(messages)[:50]:
            if not isinstance(msg, dict):
                continue
            role = msg.get("role") or ""
            content = msg.get("content") or ""
            if not isinstance(content, str):
                content = str(content)
            parts.append(f"{role} {content}".strip())
        text = "\n".join([p for p in parts if p])
        return (len(text.split()), "estimated.chat_heuristic")
    try:
        encoding = _encoding_for_model(model) or tiktoken.get_encoding("cl100k_base")
    except Exception:
        return None

    tokens_per_message, tokens_per_name, tokens_for_reply = _openai_chat_overhead(model)
    total = 0
    for msg in list(messages)[:50]:
        if not isinstance(msg, dict):
            continue
        total += tokens_per_message
        role = msg.get("role") or ""
        name = msg.get("name")
        content = msg.get("content") or ""
        if not isinstance(content, str):
            content = str(content)
        total += len(encoding.encode(str(role)))
        total += len(encoding.encode(content))
        if name:
            total += tokens_per_name
            total += len(encoding.encode(str(name)))
    total += tokens_for_reply
    return total, "estimated.tiktoken_chat"


class TokenCountingProcessor(SpanProcessor):
    """
    A processor that infers token counts when not provided by the LLM response.
    It prefers a model-specific tokenizer (tiktoken) when available.
    """

    def on_end(self, span) -> None:
        prompt = span.attributes.get("llm.prompt")
        completion = span.attributes.get("llm.completion")
        model = span.attributes.get("llm.model")
        openai_messages = span.attributes.get("llm.openai.messages")

        wrote_any = False
        wrote_prompt = False
        wrote_completion = False

        if "llm.usage.prompt_tokens" not in span.attributes:
            # Prefer chat-structure estimation when available.
            est = estimate_openai_chat_prompt_tokens_with_source(openai_messages, model)
            if est is not None:
                count, source = est
                span.set_attribute("llm.usage.prompt_tokens", count)
                span.set_attribute("llm.usage.prompt_source", source)
                wrote_any = True
                wrote_prompt = True
            elif isinstance(prompt, str):
                count, source = estimate_tokens_from_text_with_source(prompt, model)
                span.set_attribute("llm.usage.prompt_tokens", count)
                span.set_attribute("llm.usage.prompt_source", source)
                wrote_any = True
                wrote_prompt = True

        if "llm.usage.completion_tokens" not in span.attributes and isinstance(completion, str):
            count, source = estimate_tokens_from_text_with_source(completion, model)
            span.set_attribute("llm.usage.completion_tokens", count)
            span.set_attribute("llm.usage.completion_source", source)
            wrote_any = True
            wrote_completion = True

        # Synthesize overall usage source if not provided by instrumentation.
        if wrote_any and "llm.usage.source" not in span.attributes:
            ps = span.attributes.get("llm.usage.prompt_source")
            cs = span.attributes.get("llm.usage.completion_source")
            if ps and cs and ps == cs:
                span.set_attribute("llm.usage.source", ps)
            elif ps or cs:
                span.set_attribute("llm.usage.source", "mixed")

        # If provider already marked usage as provider_usage, and we filled any missing
        # fields, mark it as mixed.
        if wrote_any and span.attributes.get("llm.usage.source") == "provider_usage":
            if wrote_prompt or wrote_completion:
                span.set_attribute("llm.usage.source", "mixed")

    def shutdown(self) -> None:
        return None

    def force_flush(self, timeout: Optional[float] = None) -> None:
        return None

