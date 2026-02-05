"""
Test script for RAG similarity search.

Demonstrates vector similarity search on ingested documents.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from rag.ingest import DocumentIngester


def main():
    """Test similarity search with various queries."""
    
    # Connect to database (port-forward to localhost:5432)
    db_conn = "host=localhost port=5432 dbname=iot_ops user=postgres password=postgres"
    
    ingester = DocumentIngester(db_conn)
    
    try:
        # Test queries
        test_queries = [
            "How to fix high vibration on CNC machine?",
            "What causes tool temperature to rise?",
            "CNC machine maintenance schedule",
            "Spindle speed specifications",
            "Emergency stop procedure"
        ]
        
        print("🔍 Testing RAG Similarity Search\n")
        print("=" * 80)
        
        for query in test_queries:
            print(f"\nQuery: \"{query}\"")
            print("-" * 80)
            
            results = ingester.search_similar(
                query=query,
                tenant_id='acme-manufacturing',  # Filter by customer
                top_k=3
            )
            
            if not results:
                print("  No results found")
                continue
            
            for i, result in enumerate(results, 1):
                print(f"\n  Result {i} (similarity: {result['similarity']:.3f})")
                print(f"  Document: {result['title']}")
                print(f"  Chunk {result['chunk_index']}:")
                # Show first 200 chars of content
                preview = result['content'][:200].replace('\n', ' ')
                print(f"  \"{preview}...\"")
        
        print("\n" + "=" * 80)
        
        # Show database stats
        stats = ingester.get_stats()
        print(f"\n📊 Database Statistics:")
        print(f"  Documents ingested: {stats['documents']}")
        print(f"  Total chunks: {stats['chunks']}")
        print(f"  Average chunk size: {stats['avg_chunk_size']} characters")
        
    finally:
        ingester.close()


if __name__ == '__main__':
    main()
