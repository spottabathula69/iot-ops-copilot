"""
Prometheus metrics for IoT Ops Copilot API.

Provides comprehensive observability including:
- RED metrics (Rate, Errors, Duration) per endpoint
- Custom quality metrics (RAG precision, citation accuracy)
- Resource metrics (GPU utilization, VRAM usage)
- Cache performance metrics

Usage:
    from metrics import (
        init_metrics,
        track_request,
        track_rag_precision,
        track_cache_hit,
        track_guardrails_rejection
    )
    
    # Initialize metrics endpoint
    init_metrics(app)
    
    # Track request
    with track_request("ask", "200"):
        # Handle request
        pass
    
    # Track quality metrics
    track_rag_precision(0.92)
    track_cache_hit(True)
"""

from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
    CollectorRegistry
)
from contextlib import contextmanager
import time
from fastapi import Response


# Create registry
registry = CollectorRegistry()

# RED Metrics (Rate, Errors, Duration)
requests_total = Counter(
    'copilot_requests_total',
    'Total number of requests by endpoint and status',
    ['endpoint', 'status_code'],
    registry=registry
)

request_duration_seconds = Histogram(
    'copilot_request_duration_seconds',
    'Request duration in seconds by endpoint',
    ['endpoint'],
    buckets=[.01, .025, .05, .075, .1, .25, .5, .75, 1.0, 2.5, 5.0, 7.5, 10.0],
    registry=registry
)

errors_total = Counter(
    'copilot_errors_total',
    'Total errors by endpoint and error type',
    ['endpoint', 'error_type'],
    registry=registry
)

# LLM Metrics
llm_tokens_total = Counter(
    'copilot_llm_tokens_total',
    'Total LLM tokens by type',
    ['token_type'],  # prompt, completion
    registry=registry
)

llm_inference_duration_seconds = Histogram(
    'copilot_llm_inference_duration_seconds',
    'LLM inference time in seconds',
    buckets=[.1, .25, .5, .75, 1.0, 2.0, 5.0, 10.0],
    registry=registry
)

# Quality Metrics
rag_precision = Gauge(
    'copilot_rag_precision',
    'Average RAG retrieval precision (relevance score)',
    registry=registry
)

citation_count = Histogram(
    'copilot_citation_count',
    'Number of citations per response',
    buckets=[0, 1, 2, 3, 4, 5, 10],
    registry=registry
)

# Cache Metrics
cache_hits_total = Counter(
    'copilot_cache_hits_total',
    'Total cache hits',
    registry=registry
)

cache_misses_total = Counter(
    'copilot_cache_misses_total',
    'Total cache misses',
    registry=registry
)

cache_hit_ratio = Gauge(
    'copilot_cache_hit_ratio',
    'Cache hit ratio (hits / total)',
    registry=registry
)

# Guardrails Metrics
guardrails_rejections_total = Counter(
    'copilot_guardrails_rejections_total',
    'Total guardrails rejections by type',
    ['rejection_type'],  # prompt_injection, pii
    registry=registry
)

# Resource Metrics
gpu_utilization_percent = Gauge(
    'copilot_gpu_utilization_percent',
    'GPU utilization percentage',
    registry=registry
)

gpu_memory_bytes = Gauge(
    'copilot_gpu_memory_bytes',
    'GPU memory usage in bytes',
    registry=registry
)


def init_metrics(app):
    """
    Add /metrics endpoint to FastAPI app for Prometheus scraping.
    
    Args:
        app: FastAPI application instance
    """
    @app.get("/metrics")
    async def metrics():
        """Prometheus metrics endpoint."""
        return Response(
            content=generate_latest(registry),
            media_type=CONTENT_TYPE_LATEST
        )
    
    print("✅ Metrics endpoint initialized: /metrics")


@contextmanager
def track_request(endpoint: str, status_code: str = "200"):
    """
    Context manager to track request duration and count.
    
    Usage:
        with track_request("ask", "200"):
            # Handle request
            pass
    
    Args:
        endpoint: Endpoint name (ask, insights, troubleshoot)
        status_code: HTTP status code
    """
    start_time = time.time()
    try:
        yield
        # Success
        requests_total.labels(endpoint=endpoint, status_code=status_code).inc()
    except Exception as e:
        # Error
        error_type = type(e).__name__
        requests_total.labels(endpoint=endpoint, status_code="500").inc()
        errors_total.labels(endpoint=endpoint, error_type=error_type).inc()
        raise
    finally:
        # Track duration regardless of success/failure
        duration = time.time() - start_time
        request_duration_seconds.labels(endpoint=endpoint).observe(duration)


def track_llm_tokens(prompt_tokens: int, completion_tokens: int):
    """
    Track LLM token usage.
    
    Args:
        prompt_tokens: Number of tokens in prompt
        completion_tokens: Number of tokens in completion
    """
    llm_tokens_total.labels(token_type="prompt").inc(prompt_tokens)
    llm_tokens_total.labels(token_type="completion").inc(completion_tokens)


def track_llm_inference(duration_seconds: float):
    """
    Track LLM inference duration.
    
    Args:
        duration_seconds: Inference time in seconds
    """
    llm_inference_duration_seconds.observe(duration_seconds)


def track_rag_precision(precision_score: float):
    """
    Track RAG retrieval precision (average relevance score).
    
    Args:
        precision_score: Average relevance score (0-1)
    """
    rag_precision.set(precision_score)


def track_citations(num_citations: int):
    """
    Track number of citations in response.
    
    Args:
        num_citations: Number of citations
    """
    citation_count.observe(num_citations)


def track_cache_hit(is_hit: bool):
    """
    Track cache hit or miss.
    
    Args:
        is_hit: True if cache hit, False if miss
    """
    if is_hit:
        cache_hits_total.inc()
    else:
        cache_misses_total.inc()
    
    # Update hit ratio
    hits = cache_hits_total._value.get()
    misses = cache_misses_total._value.get()
    total = hits + misses
    if total > 0:
        cache_hit_ratio.set(hits / total)


def track_guardrails_rejection(rejection_type: str):
    """
    Track guardrails rejection.
    
    Args:
        rejection_type: Type of rejection (prompt_injection, pii)
    """
    guardrails_rejections_total.labels(rejection_type=rejection_type).inc()


def track_gpu_utilization(utilization_percent: float, memory_bytes: int = None):
    """
    Track GPU utilization and memory usage.
    
    Args:
        utilization_percent: GPU utilization (0-100)
        memory_bytes: GPU memory usage in bytes (optional)
    """
    gpu_utilization_percent.set(utilization_percent)
    if memory_bytes is not None:
        gpu_memory_bytes.set(memory_bytes)


# Example usage in main.py:
# 
# from metrics import init_metrics, track_request, track_rag_precision, track_cache_hit
# 
# # Initialize
# init_metrics(app)
# 
# @app.post("/ask")
# async def ask(request: AskRequest):
#     with track_request("ask", "200"):
#         # Check cache
#         cached = cache.get(key)
#         track_cache_hit(cached is not None)
#         
#         if cached:
#             return cached
#         
#         # RAG search
#         candidates = rag_engine.search(...)
#         avg_score = sum(c.score for c in candidates) / len(candidates)
#         track_rag_precision(avg_score)
#         
#         # LLM inference
#         start = time.time()
#         answer = llm.generate(prompt)
#         track_llm_inference(time.time() - start)
#         
#         # Citations
#         track_citations(len(citations))
#         
#         return response
