"""Comprehensive end-to-end tests for Traccia SDK.

These tests cover real-world usage scenarios with different exporters,
instrumentations, and configurations.
"""

import pytest
import tempfile
import os
import time
from pathlib import Path

import traccia
from traccia import observe
from traccia.config import load_config, validate_config
from traccia.errors import ConfigError


class TestInstrumentation:
    """Test different instrumentation scenarios."""
    
    def test_observe_decorator_basic(self):
        """Test @observe decorator on simple functions."""
        @observe(name="add_numbers")
        def add(a: int, b: int) -> int:
            return a + b
        
        result = add(5, 3)
        assert result == 8
    
    def test_observe_decorator_with_attributes(self):
        """Test @observe decorator with custom attributes."""
        @observe(
            name="process_data",
            attributes={"component": "processor", "version": "1.0"}
        )
        def process(data: str) -> str:
            return data.upper()
        
        result = process("hello")
        assert result == "HELLO"
    
    def test_observe_decorator_with_tags(self):
        """Test @observe decorator with custom tags."""
        from traccia.context import get_current_span

        captured_tags = {}

        @observe(
            name="tagged_function",
            tags=["ingest", "critical"],
        )
        def tagged():
            span = get_current_span()
            assert span is not None
            # Access attributes to force sync from underlying OTel span
            attrs = span.attributes
            captured_tags["value"] = attrs.get("span.tags")
            return "ok"

        result = tagged()
        assert result == "ok"
        # OpenTelemetry may normalize list attributes to tuples internally
        assert list(captured_tags["value"]) == ["ingest", "critical"]
    
    def test_observe_decorator_skip_args(self):
        """Test @observe decorator with argument skipping."""
        @observe(name="login", skip_args=["password"])
        def login(username: str, password: str) -> bool:
            return username == "admin" and password == "secret"
        
        result = login("admin", "secret")
        assert result is True
    
    def test_observe_decorator_skip_result(self):
        """Test @observe decorator with result skipping."""
        @observe(name="get_token", skip_result=True)
        def get_token() -> str:
            return "sensitive-token-123"
        
        result = get_token()
        assert result == "sensitive-token-123"
    
    def test_observe_decorator_error_handling(self):
        """Test @observe decorator records errors."""
        @observe(name="failing_function")
        def fail():
            raise ValueError("Test error message")
        
        with pytest.raises(ValueError, match="Test error message"):
            fail()


class TestRateLimiting:
    """Test rate limiting functionality."""
    
    def test_rate_limiter_drops_excess_spans(self):
        """Test that rate limiting drops spans beyond limit."""
        from traccia.processors.rate_limiter import RateLimiter
        
        # Very restrictive: 2 spans/second, no blocking
        limiter = RateLimiter(max_spans_per_second=2.0, max_block_ms=0)
        
        # Acquire 5 times
        results = [limiter.acquire() for _ in range(5)]
        
        # First 2 should succeed, rest should fail
        assert sum(results) == 2
        
        stats = limiter.get_stats()
        assert stats["total_spans"] == 5
        assert stats["dropped_spans"] == 3
    
    def test_rate_limiter_with_blocking(self):
        """Test rate limiting with short blocking period."""
        from traccia.processors.rate_limiter import RateLimiter
        
        # Allow blocking up to 100ms
        limiter = RateLimiter(max_spans_per_second=10.0, max_block_ms=100)
        
        # Should be able to acquire multiple times
        # (some may block briefly)
        results = []
        for _ in range(5):
            results.append(limiter.acquire())
        
        # Most should succeed due to blocking
        assert sum(results) >= 3


class TestConfigurationScenarios:
    """Test different configuration scenarios."""
    
    def teardown_method(self):
        """Clean up env vars after each test."""
        for key in list(os.environ.keys()):
            if key.startswith("TRACCIA_") or key.startswith("AGENT_DASHBOARD_"):
                del os.environ[key]
    
    def test_config_from_file(self):
        """Test loading configuration from TOML file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write("""
[tracing]
sample_rate = 0.7
use_otlp = false

[exporters]
enable_console = true

[instrumentation]
enable_patching = false
""")
            f.flush()
            config_file = f.name
        
        try:
            config = load_config(config_file=config_file)
            assert config.tracing.sample_rate == 0.7
            assert config.tracing.use_otlp is False
            assert config.exporters.enable_console is True
            assert config.instrumentation.enable_patching is False
        finally:
            os.unlink(config_file)
    
    def test_config_from_env_vars(self):
        """Test loading configuration from environment variables."""
        os.environ["TRACCIA_SAMPLE_RATE"] = "0.8"
        os.environ["TRACCIA_ENDPOINT"] = "http://custom:4318/v1/traces"
        os.environ["TRACCIA_DEBUG"] = "true"
        
        config = load_config()
        
        assert config.tracing.sample_rate == 0.8
        assert config.tracing.endpoint == "http://custom:4318/v1/traces"
        assert config.logging.debug is True
    
    def test_config_priority(self):
        """Test configuration priority: explicit > env > file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            f.write("""
[tracing]
sample_rate = 0.5
endpoint = "http://file:4318/v1/traces"
""")
            f.flush()
            config_file = f.name
        
        try:
            # Set env var
            os.environ["TRACCIA_SAMPLE_RATE"] = "0.7"
            
            # Explicit override
            overrides = {
                "tracing": {
                    "sample_rate": 0.9
                }
            }
            
            config = load_config(config_file=config_file, overrides=overrides)
            
            # Explicit should win
            assert config.tracing.sample_rate == 0.9
        finally:
            os.unlink(config_file)
    
    def test_invalid_config_validation(self):
        """Test that invalid configs are caught."""
        # Sample rate > 1.0
        is_valid, msg, config = validate_config(
            overrides={"tracing": {"sample_rate": 1.5}}
        )
        assert not is_valid
        assert config is None
        
        # Sample rate < 0
        is_valid, msg, config = validate_config(
            overrides={"tracing": {"sample_rate": -0.1}}
        )
        assert not is_valid
    
    def test_conflicting_exporters_validation(self):
        """Test that conflicting exporters are detected."""
        is_valid, msg, config = validate_config(
            overrides={
                "exporters": {
                    "enable_console": True,
                    "enable_file": True,
                }
            }
        )
        # Should fail - can't have multiple exporters
        assert not is_valid


class TestErrorHandling:
    """Test error handling across different scenarios."""
    
    def test_exception_in_decorated_function(self):
        """Test that exceptions are properly recorded and re-raised."""
        @observe(name="error_function")
        def raise_error():
            raise RuntimeError("Something went wrong")
        
        with pytest.raises(RuntimeError, match="Something went wrong"):
            raise_error()
    
    def test_nested_exceptions(self):
        """Test handling of nested exceptions."""
        @observe(name="outer")
        def outer():
            @observe(name="inner")
            def inner():
                raise KeyError("Inner error")
            
            try:
                inner()
            except KeyError:
                raise ValueError("Outer error")
        
        with pytest.raises(ValueError, match="Outer error"):
            outer()


class TestVersionAndBackwardCompat:
    """Test version exposure and backward compatibility."""
    
    def test_version_accessible(self):
        """Test that version is accessible."""
        assert hasattr(traccia, '__version__')
        assert isinstance(traccia.__version__, str)
        # Should follow semver pattern
        parts = traccia.__version__.split('.')
        assert len(parts) >= 2  # At least major.minor



if __name__ == "__main__":
    pytest.main([__file__, "-v"])
