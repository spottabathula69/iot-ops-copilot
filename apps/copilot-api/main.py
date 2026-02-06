"""
FastAPI Copilot Service - AI-powered IoT operations assistant.

Provides RAG-grounded Q&A, device insights, and troubleshooting guides.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import time
import sys
import os
import psycopg2

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from apps.rag.embedder import DocumentEmbedder
from apps.rag.hybrid_search import HybridSearchEngine
from apps.rag.reranker import DocumentReranker

# Import from same directory
# Using vLLM for faster GPU inference (10-20x speedup vs llama-cpp-python)
import llm_vllm as llm_module
import guardrails
import cache as cache_module

VLLMModel = llm_module.VLLMModel
MockVLLMModel = llm_module.MockVLLMModel
PromptTemplate = llm_module.PromptTemplateVLLM
Guardrails = guardrails.Guardrails
ResponseCache = cache_module.ResponseCache


# Pydantic models
class AskRequest(BaseModel):
    """Request model for /ask endpoint."""
    query: str = Field(..., description="User question")
    tenant_id: str = Field(..., description="Customer/tenant ID")
    doc_types: Optional[List[str]] = Field(None, description="Filter by document types")
    use_reranking: bool = Field(True, description="Use reranker for better precision")
    max_context: int = Field(3, description="Max context chunks to use", le=10)


class Citation(BaseModel):
    """Citation metadata."""
    title: str
    doc_type: str
    version: str
    chunk_index: int
    source_path: str
    score: float


class AskResponse(BaseModel):
    """Response model for /ask endpoint."""
    answer: str
    citations: List[Citation]
    latency_ms: int
    context_used: int


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    llm_loaded: bool
    rag_enabled: bool


class InsightsRequest(BaseModel):
    """Request model for /insights endpoint."""
    device_id: str = Field(..., description="Device ID to analyze")
    tenant_id: str = Field(..., description="Tenant ID")
    time_range_hours: int = Field(24, description="Hours of data to analyze", ge=1, le=168)


class MetricSummary(BaseModel):
    """Summary of a metric."""
    metric: str
    current_value: Optional[float]
    avg_value: Optional[float]
    threshold: Optional[float]
    status: str  # normal, warning, critical


class InsightsResponse(BaseModel):
    """Response model for /insights endpoint."""
    summary: str
    metrics: List[MetricSummary]
    recommendations: List[str]
    latency_ms: int


class TroubleshootRequest(BaseModel):
    """Request model for /troubleshoot endpoint."""
    error_code: str = Field(..., description="Error code to troubleshoot")
    tenant_id: str = Field(..., description="Tenant ID")
    device_context: Optional[str] = Field(None, description="Additional device context")


class TroubleshootStep(BaseModel):
    """A troubleshooting step."""
    step: int
    action: str
    expected_result: Optional[str] = None


class TroubleshootResponse(BaseModel):
    """Response model for /troubleshoot endpoint."""
    error_code: str
    description: str
    steps: List[TroubleshootStep]
    tools_needed: List[str]
    estimated_time: str
    citations: List[Citation]
    latency_ms: int


# Initialize FastAPI app
app = FastAPI(
    title="IoT Ops Copilot API",
    description="AI-powered operations assistant with RAG",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
class AppState:
    """Application state."""
    llm: Optional[VLLMModel] = None  # Changed from LlamaModel to VLLMModel
    embedder: Optional[DocumentEmbedder] = None
    rag_engine: Optional[HybridSearchEngine] = None
    reranker: Optional[DocumentReranker] = None
    cache: Optional[ResponseCache] = None
    db_conn: str = "host=localhost port=5432 dbname=iot_ops user=postgres password=postgres"

state = AppState()


@app.on_event("startup")
async def startup_event():
    """Initialize models on startup."""
    print("\n" + "="*80)
    print("🚀 IoT Ops Copilot API - Starting")
    print("="*80)
    
    # Initialize embedder
    print("\n📦 Loading embedding model...")
    state.embedder = DocumentEmbedder(model='local')
    
    # Initialize RAG engine
    print("\n🔍 Initializing RAG engine...")
    state.rag_engine = HybridSearchEngine(state.db_conn, state.embedder)
    
    # Initialize reranker
    print("\n🎯 Loading reranker...")
    state.reranker = DocumentReranker()
    
    # Initialize cache
    print("\n💾 Initializing response cache...")
    state.cache = ResponseCache(ttl_seconds=3600)  # 1 hour TTL
    
    # Initialize LLM
    print("\n🦙 Loading LLM...")
    try:
        # Use TinyLlama (1.1B) for fast inference, or set VLLM_MODEL_NAME env var
        model_name = os.getenv('VLLM_MODEL_NAME', 'TinyLlama/TinyLlama-1.1B-Chat-v1.0')
        print(f"   Model: {model_name}")
        state.llm = VLLMModel(model_name=model_name, max_tokens=200)
    except Exception as e:
        print(f"⚠️  Failed to load vLLM: {e}")
        print("   Using mock vLLM for testing")
        state.llm = MockVLLMModel()
    
    print("\n" + "="*80)
    print("✅ Copilot API ready!")
    print("="*80)
    print(f"\n📍 Endpoints:")
    print(f"   - POST /ask             - RAG-grounded Q&A")
    print(f"   - POST /insights        - Device health summaries")
    print(f"   - POST /troubleshoot    - Step-by-step guides")
    print(f"   - GET  /health          - Health check")
    print(f"   - GET  /docs            - API documentation")
    print()


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        llm_loaded=state.llm is not None,
        rag_enabled=state.rag_engine is not None
    )


@app.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest):
    """
    Answer questions using RAG-grounded LLM.
    
    Pipeline:
    1. Retrieve relevant chunks (hybrid search)
    2. Rerank for precision (optional)
    3. Build prompt with context
    4. Generate answer with LLM
    5. Extract citations
    """
    start_time = time.time()
    
    if not state.llm or not state.rag_engine:
        raise HTTPException(status_code=503, detail="Service not ready")
    
    try:
        # Step 1: Retrieve relevant chunks
        print(f"\n🔍 Query: {request.query}")
        print(f"   Tenant: {request.tenant_id}")
        
        # Get top 20 candidates with hybrid search
        candidates = state.rag_engine.search(
            query=request.query,
            tenant_id=request.tenant_id,
            doc_type=None,  # Could filter by request.doc_types
            top_k=20
        )
        
        print(f"   Retrieved {len(candidates)} candidates")
        
        if not candidates:
            return AskResponse(
                answer="I don't have any relevant information to answer that question.",
                citations=[],
                latency_ms=int((time.time() - start_time) * 1000),
                context_used=0
            )
        
        # Step 2: Rerank for precision (optional)
        if request.use_reranking and state.reranker:
            reranked = state.reranker.rerank(
                query=request.query,
                results=candidates,
                top_k=request.max_context
            )
            relevant_chunks = [result for result, score in reranked]
            print(f"   Reranked to top {len(relevant_chunks)}")
        else:
            relevant_chunks = candidates[:request.max_context]
        
        # Step 3: Build prompt with context
        context_texts = [chunk.content for chunk in relevant_chunks]
        citation_strs = [
            f"{chunk.title} (v{chunk.version}), {chunk.doc_type}, Chunk {chunk.chunk_index}"
            for chunk in relevant_chunks
        ]
        
        prompt = PromptTemplate.rag_qa(
            query=request.query,
            context=context_texts,
            citations=citation_strs
        )
        
        # Step 4: Generate answer
        print(f"   Generating answer with LLM...")
        answer = state.llm.generate(prompt, max_tokens=300)
        
        # Step 5: Build citations
        citations = [
            Citation(
                title=chunk.title,
                doc_type=chunk.doc_type,
                version=chunk.version,
                chunk_index=chunk.chunk_index,
                source_path=chunk.source_path,
                score=chunk.score
            )
            for chunk in relevant_chunks
        ]
        
        latency_ms = int((time.time() - start_time) * 1000)
        print(f"   ✅ Answer generated ({latency_ms}ms)")
        
        return AskResponse(
            answer=answer,
            citations=citations,
            latency_ms=latency_ms,
            context_used=len(relevant_chunks)
        )
    
    except Exception as e:
        print(f"   ❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/insights", response_model=InsightsResponse)
async def insights(request: InsightsRequest):
    """
    Get device health insights from telemetry data.
    
    Queries telemetry (or generates mock data) and uses LLM for summary.
    """
    start_time = time.time()
    
    if not state.llm:
        raise HTTPException(status_code=503, detail="LLM not ready")
    
    try:
        print(f"\n📊 Getting insights for device: {request.device_id}")
        
        # Mock telemetry data (replace with real DB query when telemetry table exists)
        # TODO: Replace with: SELECT metric, value, timestamp FROM telemetry_silver WHERE device_id = ...
        mock_telemetry = {
            "temperature": [75.2, 76.1, 77.3, 78.5, 79.2],
            "vibration": [1.8, 1.9, 2.1, 2.3, 2.5],
            "pressure": [95.1, 94.8, 94.5, 94.2, 94.0]
        }
        
        # Aggregate metrics
        metric_summaries = []
        thresholds = {
            "temperature": 80.0,
            "vibration": 2.0,
            "pressure": 100.0
        }
        
        for metric, values in mock_telemetry.items():
            current = values[-1] if values else None
            avg = sum(values) / len(values) if values else None
            threshold = thresholds.get(metric)
            
            status = "normal"
            if threshold and current:
                if current > threshold:
                    status = "critical"
                elif current > threshold * 0.8:
                    status = "warning"
            
            metric_summaries.append(MetricSummary(
                metric=metric,
                current_value=current,
                avg_value=avg,
                threshold=threshold,
                status=status
            ))
        
        # Generate summary with LLM
        metrics_text = "\n".join([
            f"- {m.metric}: current={m.current_value:.2f}, avg={m.avg_value:.2f}, threshold={m.threshold}, status={m.status}"
            for m in metric_summaries
        ])
        
        prompt = f"""<s>[INST] <<SYS>>
You are an IoT device health analyst. Analyze the telemetry data and provide a brief summary.
<</SYS>>

Device ID: {request.device_id}
Time Range: Last {request.time_range_hours} hours

Metrics:
{metrics_text}

Provide:
1. A 2-sentence summary of overall device health
2. List any concerning trends

Summary: [/INST]"""
        
        summary = state.llm.generate(prompt, max_tokens=150)
        
        # Generate recommendations for abnormal metrics
        recommendations = []
        for m in metric_summaries:
            if m.status == "critical":
                recommendations.append(f"⚠️  CRITICAL: {m.metric} at {m.current_value:.2f} exceeds threshold {m.threshold} - immediate action required")
            elif m.status == "warning":
                recommendations.append(f"⚡ WARNING: {m.metric} at {m.current_value:.2f} approaching threshold {m.threshold} - monitor closely")
        
        if not recommendations:
            recommendations.append("✅ All metrics within normal ranges - no action needed")
        
        latency_ms = int((time.time() - start_time) * 1000)
        print(f"   ✅ Insights generated ({latency_ms}ms)")
        
        return InsightsResponse(
            summary=summary,
            metrics=metric_summaries,
            recommendations=recommendations,
            latency_ms=latency_ms
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"   ❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/troubleshoot", response_model=TroubleshootResponse)
async def troubleshoot(request: TroubleshootRequest):
    """
    Generate step-by-step troubleshooting guide for error code.
    
    Uses RAG to find relevant manual sections, then LLM to structure steps.
    """
    start_time = time.time()
    
    if not state.llm or not state.rag_engine:
        raise HTTPException(status_code=503, detail="Service not ready")
    
    try:
        print(f"\n🔧 Troubleshooting: {request.error_code}")
        
        # Search for error code in manuals
        search_query = f"error code {request.error_code} troubleshooting"
        if request.device_context:
            search_query += f" {request.device_context}"
        
        candidates = state.rag_engine.search(
            query=search_query,
            tenant_id=request.tenant_id,
            doc_type="manual",
            top_k=10
        )
        
        if not candidates:
            raise HTTPException(
                status_code=404,
                detail=f"No documentation found for error code {request.error_code}"
            )
        
        # Rerank to get top 3 most relevant
        if state.reranker:
            reranked = state.reranker.rerank(search_query, candidates, top_k=3)
            relevant_chunks = [result for result, score in reranked]
        else:
            relevant_chunks = candidates[:3]
        
        # Build context
        context = "\n\n".join([chunk.content for chunk in relevant_chunks])
        
        # Generate structured troubleshooting steps
        prompt = PromptTemplate.troubleshooting(request.error_code, [context])
        
        guide_text = state.llm.generate(prompt, max_tokens=300)
        
        # Parse into structured steps (simple line-based parsing)
        steps = []
        tools = []
        estimated_time = "15-30 minutes"
        
        # Extract numbered steps from LLM response
        lines = guide_text.split("\n")
        step_num = 1
        for line in lines:
            line = line.strip()
            # Match lines starting with number or dash
            if line and (line[0].isdigit() or line.startswith("-")):
                action = line.lstrip("0123456789.-) ")
                if action and len(action) > 10:  # Filter out very short lines
                    steps.append(TroubleshootStep(
                        step=step_num,
                        action=action,
                        expected_result=None
                    ))
                    step_num += 1
        
        # Build citations
        citations = [
            Citation(
                title=chunk.title,
                doc_type=chunk.doc_type,
                version=chunk.version,
                chunk_index=chunk.chunk_index,
                source_path=chunk.source_path,
                score=chunk.score
            )
            for chunk in relevant_chunks
        ]
        
        latency_ms = int((time.time() - start_time) * 1000)
        print(f"   ✅ Guide generated with {len(steps)} steps ({latency_ms}ms)")
        
        return TroubleshootResponse(
            error_code=request.error_code,
            description=f"Troubleshooting guide for error {request.error_code}",
            steps=steps if steps else [
                TroubleshootStep(step=1, action="Follow manual instructions from citations below", expected_result=None)
            ],
            tools_needed=tools,
            estimated_time=estimated_time,
            citations=citations,
            latency_ms=latency_ms
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"   ❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
