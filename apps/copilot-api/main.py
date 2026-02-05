"""
FastAPI Copilot Service - AI-powered IoT operations assistant.

Provides RAG-grounded Q&A, device insights, and troubleshooting guides.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
import time
import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from apps.rag.embedder import DocumentEmbedder
from apps.rag.hybrid_search import HybridSearchEngine
from apps.rag.reranker import DocumentReranker

# Import from same directory  
import llm
LlamaModel = llm.LlamaModel
MockLlamaModel = llm.MockLlamaModel
PromptTemplate = llm.PromptTemplate


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
    llm: Optional[LlamaModel] = None
    embedder: Optional[DocumentEmbedder] = None
    rag_engine: Optional[HybridSearchEngine] = None
    reranker: Optional[DocumentReranker] = None
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
    
    # Initialize LLM
    print("\n🦙 Loading LLM...")
    try:
        model_path = os.getenv('LLAMA_MODEL_PATH')
        if model_path and os.path.exists(model_path):
            state.llm = LlamaModel(model_path=model_path)
        else:
            print("⚠️  No model file found, using mock LLM for testing")
            print("   Set LLAMA_MODEL_PATH env var to use real model")
            state.llm = MockLlamaModel()
    except Exception as e:
        print(f"⚠️  Failed to load LLM: {e}")
        print("   Using mock LLM for testing")
        state.llm = MockLlamaModel()
    
    print("\n" + "="*80)
    print("✅ Copilot API ready!")
    print("="*80)
    print(f"\n📍 Endpoints:")
    print(f"   - POST /ask             - RAG-grounded Q&A")
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
