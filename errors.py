"""Traccia SDK error hierarchy and exceptions."""

from __future__ import annotations


class TracciaError(Exception):
    """Base exception for all Traccia SDK errors."""
    
    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
    
    def __str__(self) -> str:
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({details_str})"
        return self.message


class ConfigError(TracciaError):
    """Raised when configuration is invalid or conflicting."""
    pass


class ValidationError(TracciaError):
    """Raised when validation fails."""
    pass


class ExportError(TracciaError):
    """Raised when span export fails."""
    pass


class RateLimitError(TracciaError):
    """Raised when rate limit is exceeded (in strict mode)."""
    pass


class InitializationError(TracciaError):
    """Raised when SDK initialization fails."""
    pass


class InstrumentationError(TracciaError):
    """Raised when instrumentation/patching fails."""
    pass
