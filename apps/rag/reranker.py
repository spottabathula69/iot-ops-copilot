"""
Cross-encoder reranking for improved retrieval precision.

Uses a pre-trained cross-encoder model to score query-document pairs.
"""

from typing import List, Tuple
from dataclasses import dataclass


@dataclass
class RankedResult:
    """Result with reranking score."""
    content: str
    score: float
    metadata: dict


class DocumentReranker:
    """
    Rerank search results using cross-encoder model.
    
    Cross-encoders score query-document pairs jointly, providing
    better precision than bi-encoders (separate query/doc encoding).
    """
    
    def __init__(self, model_name: str = 'cross-encoder/ms-marco-MiniLM-L-6-v2'):
        """
        Initialize reranker.
        
        Args:
            model_name: HuggingFace model name for cross-encoder
        """
        from sentence_transformers import CrossEncoder
        
        print(f"Loading reranker model ({model_name})...")
        self.model = CrossEncoder(model_name)
        print(f"✅ Loaded reranker model")
    
    def rerank(self, 
               query: str, 
               results: List,
               top_k: int = 5) -> List[Tuple[any, float]]:
        """
        Rerank search results.
        
        Args:
            query: Search query
            results: List of result objects (must have .content attribute)
            top_k: Number of top results to return
        
        Returns:
            List of (result, score) tuples sorted by score descending
        """
        if not results:
            return []
        
        # Create query-document pairs
        pairs = [(query, r.content) for r in results]
        
        # Score all pairs
        scores = self.model.predict(pairs)
        
        # Combine results with scores and sort
        ranked = list(zip(results, scores))
        ranked.sort(key=lambda x: x[1], reverse=True)
        
        return ranked[:top_k]
    
    def rerank_with_details(self,
                           query: str,
                           results: List,
                           top_k: int = 5) -> List[RankedResult]:
        """
        Rerank and return detailed results.
        
        Args:
            query: Search query
            results: List of result objects
            top_k: Number of results to return
        
        Returns:
            List of RankedResult objects
        """
        reranked = self.rerank(query, results, top_k)
        
        return [
            RankedResult(
                content=result.content,
                score=float(score),
                metadata={
                    'document_id': result.document_id,
                    'chunk_index': result.chunk_index,
                    'title': result.title,
                    'doc_type': result.doc_type,
                    'version': result.version,
                    'source_path': result.source_path
                }
            )
            for result, score in reranked
        ]
