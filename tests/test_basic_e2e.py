"""Basic smoke tests for Traccia SDK.

Quick sanity checks that core functionality works. For comprehensive tests,
see test_comprehensive_e2e.py.
"""

import pytest

import traccia
from traccia import observe


def test_version_exposed():
    """Smoke test: version is accessible."""
    assert hasattr(traccia, '__version__')
    assert isinstance(traccia.__version__, str)
    assert len(traccia.__version__) > 0


def test_import_observe():
    """Smoke test: @observe decorator can be imported and used."""
    @observe(name="test_function")
    def simple_function(x: int, y: int) -> int:
        return x + y
    
    result = simple_function(2, 3)
    assert result == 5


def test_import_init():
    """Smoke test: init can be imported."""
    from traccia import init, stop_tracing
    
    # Just test import, actual init tested in comprehensive tests
    assert init is not None
    assert stop_tracing is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
