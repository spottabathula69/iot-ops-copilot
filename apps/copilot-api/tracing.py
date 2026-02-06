"""
Distributed tracing instrumentation using OpenTelemetry + Jaeger.

Provides end-to-end request tracing across:
- API endpoints (automatic via FastAPI instrumentation)
- Guardrails checks
- Cache lookups
- RAG search (BM25 + Vector + Reranking)
- vLLM inference

Usage:
    from tracing import (
        init_tracing,
        trace_guardrails_check,
        trace_cache_lookup,
        trace_rag_search,
        trace_reranking,
        trace_llm_generate
    )
    
    # Initialize during app startup
    tracer = init_tracing(app, service_name="copilot-api")
    
    # Use in endpoints
    @app.post("/ask")
    async def ask(request: AskRequest):
        with trace_guardrails_check(tracer, request.query):
            guardrails.check(request.query)
        
        with trace_cache_lookup(tracer, cache_key):
            cached = cache.get(cache_key)
        
        with trace_rag_search(tracer, request.query, top_k=20):
            candidates = rag_engine.search(...)
        
        with trace_llm_generate(tracer, len(prompt), max_tokens=200):
            answer = llm.generate(prompt)
"""

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.trace import Status, StatusCode

import os


def init_tracing(app, service_name="copilot-api"):
    """
    Initialize OpenTelemetry tracing with Jaeger backend.
    
    Automatically instruments FastAPI app to trace all requests.
    Custom spans can be added for specific operations.
    
    Args:
        app: FastAPI application instance
        service_name: Service name for traces
    
    Returns:
        Tracer instance for creating custom spans
    
    Environment Variables:
        JAEGER_HOST: Jaeger agent hostname (default: jaeger.monitoring.svc.cluster.local)
        JAEGER_PORT: Jaeger agent port (default: 6831)
        TRACING_ENABLED: Enable/disable tracing (default: true)
    """
    # Check if tracing is enabled
    if os.getenv("TRACING_ENABLED", "true").lower() == "false":
        print("⚠️  Tracing disabled (TRACING_ENABLED=false)")
        return None
    
    # Get Jaeger endpoint from environment
    jaeger_host = os.getenv("JAEGER_HOST", "jaeger.monitoring.svc.cluster.local")
    jaeger_port = int(os.getenv("JAEGER_PORT", "6831"))
    
    # Create resource with service name
    resource = Resource(attributes={
        SERVICE_NAME: service_name
    })
    
    # Create tracer provider
    provider = TracerProvider(resource=resource)
    
    try:
        # Create Jaeger exporter
        jaeger_exporter = JaegerExporter(
            agent_host_name=jaeger_host,
            agent_port=jaeger_port,
        )
        
        # Add span processor
        provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
        
        # Set global tracer provider
        trace.set_tracer_provider(provider)
        
        # Auto-instrument FastAPI (traces all routes automatically)
        FastAPIInstrumentor.instrument_app(app)
        
        print(f"✅ Tracing initialized: {service_name} → {jaeger_host}:{jaeger_port}")
        
    except Exception as e:
        print(f"⚠️  Failed to initialize tracing: {e}")
        print("   Continuing without tracing...")
        return None
    
    return trace.get_tracer(__name__)


def trace_guardrails_check(tracer, query: str):
    """
    Create span for guardrails validation.
    
    Attributes:
        - query_length: Length of query being validated
    
    Args:
        tracer: OpenTelemetry tracer instance
        query: Query string being validated
    
    Returns:
        Context manager for the span
    
    Usage:
        with trace_guardrails_check(tracer, query):
            result = guardrails.check(query)
    """
    if tracer is None:
        from contextlib import nullcontext
        return nullcontext()
    
    return tracer.start_as_current_span(
        "guardrails.check",
        attributes={
            "query_length": len(query),
        }
    )


def trace_cache_lookup(tracer, cache_key: str):
    """
    Create span for cache lookup.
    
    Attributes:
        - cache_key: Truncated cache key (for privacy)
    
    Args:
        tracer: OpenTelemetry tracer instance
        cache_key: Cache key being looked up
    
    Returns:
        Context manager for the span
    
    Usage:
        with trace_cache_lookup(tracer, key):
            cached = cache.get(key)
    """
    if tracer is None:
        from contextlib import nullcontext
        return nullcontext()
    
    return tracer.start_as_current_span(
        "cache.lookup",
        attributes={
            "cache_key": cache_key[:16] + "...",  # Truncate for privacy
        }
    )


def trace_rag_search(tracer, query: str, top_k: int):
    """
    Create span for RAG hybrid search.
    
    Attributes:
        - query: Truncated query (100 chars max)
        - top_k: Number of results requested
        - search_type: Always "hybrid" for our implementation
    
    Args:
        tracer: OpenTelemetry tracer instance
        query: Search query
        top_k: Number of results to return
    
    Returns:
        Context manager for the span
    
    Usage:
        with trace_rag_search(tracer, query, top_k=20):
            candidates = rag_engine.search(query, top_k=top_k)
    """
    if tracer is None:
        from contextlib import nullcontext
        return nullcontext()
    
    return tracer.start_as_current_span(
        "rag.search",
        attributes={
            "query": query[:100],  # Truncate
            "top_k": top_k,
            "search_type": "hybrid",
        }
    )


def trace_reranking(tracer, num_candidates: int, top_k: int):
    """
    Create span for cross-encoder reranking.
    
    Attributes:
        - num_candidates: Number of candidates to rerank
        - top_k: Number of top results to keep
    
    Args:
        tracer: OpenTelemetry tracer instance
        num_candidates: Number of search results to rerank
        top_k: Number of top results after reranking
    
    Returns:
        Context manager for the span
    
    Usage:
        with trace_reranking(tracer, len(candidates), top_k=3):
            reranked = reranker.rerank(query, candidates, top_k=top_k)
    """
    if tracer is None:
        from contextlib import nullcontext
        return nullcontext()
    
    return tracer.start_as_current_span(
        "rag.rerank",
        attributes={
            "num_candidates": num_candidates,
            "top_k": top_k,
        }
    )


def trace_llm_generate(tracer, prompt_length: int, max_tokens: int):
    """
    Create span for LLM generation.
    
    Attributes:
        - prompt_length: Length of prompt in characters
        - max_tokens: Maximum tokens to generate
        - model: Model type (vllm)
    
    Args:
        tracer: OpenTelemetry tracer instance
        prompt_length: Length of prompt
        max_tokens: Max tokens for generation
    
    Returns:
        Context manager for the span
    
    Usage:
        with trace_llm_generate(tracer, len(prompt), max_tokens=200):
            answer = llm.generate(prompt, max_tokens=max_tokens)
    """
    if tracer is None:
        from contextlib import nullcontext
        return nullcontext()
    
    return tracer.start_as_current_span(
        "llm.generate",
        attributes={
            "prompt_length": prompt_length,
            "max_tokens": max_tokens,
            "model": "vllm",
        }
    )


def set_span_error(span, error: Exception):
    """
    Mark current span as error and add exception details.
    
    Args:
        span: Current span
        error: Exception that occurred
    
    Usage:
        with tracer.start_as_current_span("operation") as span:
            try:
                # Do work
                pass
            except Exception as e:
                set_span_error(span, e)
                raise
    """
    if span is not None:
        span.set_status(Status(StatusCode.ERROR, str(error)))
        span.record_exception(error)


# Trace visualization example (Jaeger UI):
# 
# Request: POST /ask (810ms total)
# ├─ POST /ask                    [FastAPI auto-instrumented]
# │  ├─ guardrails.check:    2ms  [Custom span]
# │  ├─ cache.lookup:        1ms  [Custom span]
# │  ├─ rag.search:        120ms  [Custom span]
# │  ├─ rag.rerank:         35ms  [Custom span]
# │  └─ llm.generate:      648ms  [Custom span]
# 
# Clicking any span shows:
# - Start time, duration
# - Attributes (query_length, top_k, etc.)
# - Tags (http.method, http.route, etc.)
# - Logs/events
# - Stack trace (if error)
