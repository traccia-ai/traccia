"""
FastAPI middleware helpers for tracing HTTP requests with the SDK.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from traccia.instrumentation import start_server_span


def install_http_middleware(app: Any, *, tracer_name: str = "agents-fastapi") -> None:
    """
    Attach an HTTP middleware that wraps each FastAPI request in a server span.

    - Propagates incoming context from headers
    - Records method/path and response status code
    """

    @app.middleware("http")
    async def tracing_middleware(request, call_next: Callable[[Any], Awaitable[Any]]):  # type: ignore
        # Lazy import to avoid circular import when traccia initializes.
        from traccia import get_tracer
        tracer = get_tracer(tracer_name)
        headers = dict(request.headers)
        attrs = {
            "http.method": request.method,
            "http.target": request.url.path,
        }
        async with start_server_span(tracer, "http.request", headers, attributes=attrs) as span:
            response = await call_next(request)
            try:
                span.set_attribute("http.status_code", response.status_code)
            except Exception:
                pass
            return response

    return None
