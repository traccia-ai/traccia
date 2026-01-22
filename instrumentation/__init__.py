"""Instrumentation helpers and monkey patching."""

from traccia.instrumentation.decorator import observe
from traccia.instrumentation.openai import patch_openai
from traccia.instrumentation.anthropic import patch_anthropic
from traccia.instrumentation.requests import patch_requests
from traccia.instrumentation.http_client import inject_headers as inject_http_headers
from traccia.instrumentation.http_server import extract_parent_context, start_server_span
from traccia.instrumentation.fastapi import install_http_middleware

__all__ = [
    "observe",
    "patch_openai",
    "patch_anthropic",
    "patch_requests",
    "inject_http_headers",
    "extract_parent_context",
    "start_server_span",
    "install_http_middleware",
]
