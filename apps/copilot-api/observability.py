"""
Simple wrapper to add metrics and tracing to existing endpoint logic.

Usage:
    from observability_wrapper import add_observability
    
    @app.post("/ask")
    async def ask(request: AskRequest):
        with add_observability("ask", tracer):
            # existing endpoint logic
            return response
"""

import time
from contextlib import contextmanager
import metrics
import tracing as tracing_module


@contextmanager
def add_observ(endpoint_name: str, tracer_instance):
    """
    Simple context manager to track metrics and create trace span.
    
    Usage:
        with add_observ("ask", tracer):
            # endpoint code
            return response
    """
    start_time = time.time()
    
    # Start trace span
    span_context = tracer_instance.start_as_current_span(f"/{endpoint_name}") if tracer_instance else None
    
    try:
        if span_context:
            with span_context:
                yield
        else:
            yield
        
        # Success - track metrics
        duration = time.time() - start_time
        metrics.request_duration_seconds.labels(endpoint=endpoint_name).observe(duration)
        metrics.requests_total.labels(endpoint=endpoint_name, status_code="200").inc()
    
    except Exception as e:
        # Error - track metrics
        duration = time.time() - start_time
        metrics.request_duration_seconds.labels(endpoint=endpoint_name).observe(duration)
        metrics.requests_total.labels(endpoint=endpoint_name, status_code="500").inc()
        metrics.errors_total.labels(endpoint=endpoint_name, error_type=type(e).__name__).inc()
        raise
