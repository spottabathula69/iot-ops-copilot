"""
Test hybrid search and reranking with comparative benchmarks.

Compares:
- Vector-only search
- Hybrid search (BM25 + vector)
- Hybrid + reranking
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from rag.embedder import DocumentEmbedder
from rag.hybrid_search import HybridSearchEngine
from rag.reranker import DocumentReranker


def test_vector_only(query: str, embedder, db_conn: str, tenant_id: str = None):
    """Test vector-only search."""
    engine = HybridSearchEngine(db_conn, embedder)
    
    # Use only vector search
    results = engine._search_vector(query, tenant_id, doc_type=None, top_k=5)
    
    print(f"\n{'='*80}")
    print(f"VECTOR-ONLY: \"{query}\"")
    print(f"{'='*80}")
    
    for i, r in enumerate(results, 1):
        print(f"\n  {i}. {r.title} (chunk {r.chunk_index}) - Score: {r.score:.4f}")
        print(f"     {r.content[:150]}...")
    
    engine.close()
    return results


def test_hybrid(query: str, embedder, db_conn: str, tenant_id: str = None):
    """Test hybrid search (BM25 + vector)."""
    engine = HybridSearchEngine(db_conn, embedder)
    
    results = engine.search(query, tenant_id, doc_type=None, top_k=5)
    
    print(f"\n{'='*80}")
    print(f"HYBRID (BM25 + Vector): \"{query}\"")
    print(f"{'='*80}")
    
    for i, r in enumerate(results, 1):
        print(f"\n  {i}. {r.title} (chunk {r.chunk_index}) - RRF Score: {r.score:.4f}")
        print(f"     {r.content[:150]}...")
    
    engine.close()
    return results


def test_hybrid_with_reranking(query: str, embedder, reranker, db_conn: str, tenant_id: str = None):
    """Test hybrid search + reranking."""
    engine = HybridSearchEngine(db_conn, embedder)
    
    # Get top 20 candidates from hybrid search
    candidates = engine.search(query, tenant_id, doc_type=None, top_k=20)
    
    # Rerank to top 5
    reranked = reranker.rerank(query, candidates, top_k=5)
    
    print(f"\n{'='*80}")
    print(f"HYBRID + RERANKING: \"{query}\"")
    print(f"{'='*80}")
    
    for i, (result, score) in enumerate(reranked, 1):
        print(f"\n  {i}. {result.title} (chunk {result.chunk_index}) - Rerank Score: {score:.4f}")
        print(f"     {result.content[:150]}...")
    
    engine.close()
    return reranked


def main():
    """Run comparative benchmarks."""
    
    # Connect to database (port-forward to localhost:5432)
    db_conn = "host=localhost port=5432 dbname=iot_ops user=postgres password=postgres"
    
    # Initialize models (local, no API keys!)
    print("Loading models...")
    embedder = DocumentEmbedder(model='local')
    reranker = DocumentReranker()
    
    print("\n" + "="*80)
    print("🔍 COMPARATIVE RAG SEARCH BENCHMARK")
    print("="*80)
    
    # Test queries with different characteristics
    test_queries = [
        {
            "query": "VIB_HIGH_001 error code",
            "type": "Keyword-heavy (BM25 should excel)",
            "tenant": "acme-manufacturing"
        },
        {
            "query": "Machine is shaking and making noise",
            "type": "Semantic (Vector should excel)",
            "tenant": "acme-manufacturing"
        },
        {
            "query": "How to reduce vibration during cutting operations?",
            "type": "Hybrid (Both BM25 and vector needed)",
            "tenant": "acme-manufacturing"
        }
    ]
    
    for test_case in test_queries:
        query = test_case["query"]
        tenant = test_case["tenant"]
        
        print(f"\n\n{'#'*80}")
        print(f"# TEST: {test_case['type']}")
        print(f"# Query: \"{query}\"")
        print(f"{'#'*80}")
        
        # Test all 3 methods
        vector_results = test_vector_only(query, embedder, db_conn, tenant)
        hybrid_results = test_hybrid(query, embedder, db_conn, tenant)
        reranked_results = test_hybrid_with_reranking(query, embedder, reranker, db_conn, tenant)
        
        print(f"\n{'='*80}")
        print("SUMMARY:")
        print(f"  - Vector-only: {len(vector_results)} results")
        print(f"  - Hybrid: {len(hybrid_results)} results")
        print(f"  - Hybrid + Reranking: {len(reranked_results)} results")
        print(f"{'='*80}")
    
    print("\n\n✅ Benchmark complete!")
    print("\nExpected observations:")
    print("  1. Keyword queries (VIB_HIGH_001): BM25 component helps hybrid find exact match")
    print("  2. Semantic queries (shaking/noise): Vector performs well, hybrid comparable")
    print("  3. Complex queries: Hybrid + reranking gives best precision")


if __name__ == '__main__':
    main()
