"""Tests for backward compatibility between init() and start_tracing()."""

import unittest
import logging
from traccia import start_tracing, stop_tracing, init, get_tracer


class TestBackwardCompatibility(unittest.TestCase):
    """Test backward compatibility of init() with start_tracing()."""
    
    def tearDown(self):
        """Clean up after each test."""
        try:
            stop_tracing()
        except Exception:
            pass
    
    def test_start_tracing_still_works(self):
        """Test that start_tracing() works exactly as before."""
        provider = start_tracing(
            enable_patching=False,
            enable_console_exporter=True,
        )
        
        self.assertIsNotNone(provider)
        
        # Should be able to get tracer
        tracer = get_tracer("test")
        self.assertIsNotNone(tracer)
        
        # Should be able to create spans
        with tracer.start_as_current_span("test-span"):
            pass
    
    def test_init_is_additive(self):
        """Test that init() doesn't break existing code."""
        provider = init(
            enable_patching=False,
            enable_console_exporter=True,
            auto_start_trace=False,  # Disable auto-start for this test
        )
        
        self.assertIsNotNone(provider)
        
        # Should work exactly like start_tracing()
        tracer = get_tracer("test")
        self.assertIsNotNone(tracer)
        
        with tracer.start_as_current_span("test-span"):
            pass
    
    def test_init_after_start_tracing_warns(self):
        """Test that calling init() after start_tracing() logs a warning."""
        # Set up logging capture
        log_capture = []
        handler = logging.Handler()
        handler.emit = lambda record: log_capture.append(record)
        handler.setLevel(logging.WARNING)
        logger = logging.getLogger("traccia.auto")
        logger.addHandler(handler)
        logger.setLevel(logging.WARNING)
        
        try:
            # First call start_tracing
            provider1 = start_tracing(enable_patching=False)
            self.assertIsNotNone(provider1)
            
            # Then call init() - should warn
            provider2 = init(enable_patching=False)
            
            # Should return same provider
            self.assertIs(provider2, provider1)
            
            # Should have logged warning
            self.assertTrue(any("start_tracing" in record.getMessage() for record in log_capture))
        finally:
            logger.removeHandler(handler)
    
    def test_start_tracing_after_init_warns(self):
        """Test that calling start_tracing() after init() logs a warning."""
        # Set up logging capture
        log_capture = []
        handler = logging.Handler()
        handler.emit = lambda record: log_capture.append(record)
        handler.setLevel(logging.WARNING)
        logger = logging.getLogger("traccia.auto")
        logger.addHandler(handler)
        logger.setLevel(logging.WARNING)
        
        try:
            # First call init
            provider1 = init(enable_patching=False, auto_start_trace=False)
            self.assertIsNotNone(provider1)
            
            # Then call start_tracing() - should warn
            provider2 = start_tracing(enable_patching=False)
            
            # Should return same provider
            self.assertIs(provider2, provider1)
            
            # Should have logged warning
            self.assertTrue(any("init()" in record.getMessage() for record in log_capture))
        finally:
            logger.removeHandler(handler)
    
    def test_stop_tracing_allows_reinit(self):
        """Test that stop_tracing() allows re-initialization."""
        # First initialization
        provider1 = start_tracing(enable_patching=False)
        self.assertIsNotNone(provider1)
        
        # Stop tracing
        stop_tracing()
        
        # Should be able to init again without warning
        provider2 = init(enable_patching=False, auto_start_trace=False)
        self.assertIsNotNone(provider2)
    
    def test_multiple_init_calls_idempotent(self):
        """Test that multiple init() calls are idempotent."""
        provider1 = init(enable_patching=False, auto_start_trace=False)
        provider2 = init(enable_patching=False, auto_start_trace=False)
        
        # Should return same provider
        self.assertIs(provider2, provider1)
    
    def test_multiple_start_tracing_calls_idempotent(self):
        """Test that multiple start_tracing() calls are idempotent."""
        provider1 = start_tracing(enable_patching=False)
        provider2 = start_tracing(enable_patching=False)
        
        # Should return same provider
        self.assertIs(provider2, provider1)


if __name__ == "__main__":
    unittest.main()
