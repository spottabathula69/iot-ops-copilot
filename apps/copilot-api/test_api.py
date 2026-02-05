"""
Test copilot API /ask endpoint with sample queries.
"""

import requests
import json


API_URL = "http://localhost:8000"


def test_ask(query: str, tenant_id: str = "acme-manufacturing"):
    """Test /ask endpoint."""
    print(f"\n{'='*80}")
    print(f"Query: {query}")
    print(f"{'='*80}")
    
    response = requests.post(
        f"{API_URL}/ask",
        json={
            "query": query,
            "tenant_id": tenant_id,
            "use_reranking": True,
            "max_context": 3
        }
    )
    
    if response.status_code != 200:
        print(f"❌ Error {response.status_code}: {response.text}")
        return
    
    result = response.json()
    
    print(f"\n📝 Answer:")
    print(f"{result['answer']}\n")
    
    print(f"📚 Citations ({len(result['citations'])}):")
    for i, citation in enumerate(result['citations'], 1):
        print(f"  [{i}] {citation['title']} (v{citation['version']})")
        print(f"      {citation['doc_type']}, Chunk {citation['chunk_index']}, Score: {citation['score']:.4f}")
    
    print(f"\n⏱️  Latency: {result['latency_ms']}ms")
    print(f"📊 Context used: {result['context_used']} chunks")


def test_health():
    """Test health endpoint."""
    response = requests.get(f"{API_URL}/health")
    print(f"\n🏥 Health check: {response.json()}")


def main():
    """Run test queries."""
    print("\n" + "="*80)
    print("🧪 Testing Copilot API")
    print("="*80)
    
    # Health check
    test_health()
    
    # Test queries
    queries = [
        "How do I fix high vibration on the CNC machine?",
        "What does error code VIB_HIGH_001 mean?",
        "What is the recommended spindle speed for aluminum?",
        "How often should I perform maintenance on the Haas VF-2?"
    ]
    
    for query in queries:
        try:
            test_ask(query)
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print("\n" + "="*80)
    print("✅ Tests complete")
    print("="*80)


if __name__ == "__main__":
    main()
