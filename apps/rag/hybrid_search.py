"""
Hybrid search combining BM25 (keyword) and vector (semantic) retrieval.

Uses Reciprocal Rank Fusion (RRF) to merge results from both methods.
"""

from typing import List, Dict, Optional
import psycopg2
from dataclasses import dataclass


@dataclass
class SearchResult:
    """Result from hybrid search with citation metadata."""
    document_id: str
    chunk_index: int
    content: str
    score: float
    title: str
    doc_type: str
    version: str
    source_path: str
    tenant_id: str


@dataclass
class Citation:
    """Citation metadata for result attribution."""
    title: str
    doc_type: str
    version: str
    chunk_index: int
    source_path: str
    
    def format(self, index: int) -> str:
        """Format citation for display."""
        return f"[{index}] {self.title} (v{self.version}), {self.doc_type}, Chunk {self.chunk_index}\n    Source: {self.source_path}"


class HybridSearchEngine:
    """
    Hybrid search combining BM25 and vector similarity.
    
    Uses Reciprocal Rank Fusion (RRF) to merge rankings from:
    - BM25: Keyword-based full-text search (Postgres tsvector)
    - Vector: Semantic similarity search (pgvector)
    """
    
    def __init__(self, db_conn_string: str, embedder=None):
        """
        Initialize hybrid search engine.
        
        Args:
            db_conn_string: PostgreSQL connection string
            embedder: DocumentEmbedder instance for query embedding
        """
        self.conn = psycopg2.connect(db_conn_string)
        self.embedder = embedder
    
    def search(self, 
               query: str, 
               tenant_id: Optional[str] = None,
               doc_type: Optional[str] = None,
               top_k: int = 10,
               bm25_weight: float = 0.5,
               vector_weight: float = 0.5) -> List[SearchResult]:
        """
        Perform hybrid search using RRF fusion.
        
        Args:
            query: Search query
            tenant_id: Filter by tenant (optional)
            doc_type: Filter by document type (optional)
            top_k: Number of results to return
            bm25_weight: Weight for BM25 scores (0-1)
            vector_weight: Weight for vector scores (0-1)
        
        Returns:
            List of SearchResult objects sorted by fused score
        """
        # Get results from both methods (top 20 candidates for fusion)
        bm25_results = self._search_bm25(query, tenant_id, doc_type, top_k=20)
        vector_results = self._search_vector(query, tenant_id, doc_type, top_k=20)
        
        # Apply RRF fusion
        fused_results = self._reciprocal_rank_fusion(
            bm25_results, 
            vector_results,
            bm25_weight=bm25_weight,
            vector_weight=vector_weight
        )
        
        return fused_results[:top_k]
    
    def _search_bm25(self, 
                     query: str, 
                     tenant_id: Optional[str],
                     doc_type: Optional[str],
                     top_k: int = 20) -> List[SearchResult]:
        """
        BM25 keyword search using Postgres full-text search.
        
        Uses ts_rank_cd() for BM25-like scoring.
        """
        # Convert query to tsquery
        sql = """
            SELECT 
                document_id, chunk_index, content, title, doc_type, 
                version, source_path, tenant_id,
                ts_rank_cd(content_tsvector, query) AS rank
            FROM document_embeddings, 
                 plainto_tsquery('english', %s) query
            WHERE content_tsvector @@ query
        """
        params = [query]
        
        if tenant_id:
            sql += " AND tenant_id = %s"
            params.append(tenant_id)
        
        if doc_type:
            sql += " AND doc_type = %s"
            params.append(doc_type)
        
        sql += " ORDER BY rank DESC LIMIT %s"
        params.append(top_k)
        
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        
        return [
            SearchResult(
                document_id=row[0],
                chunk_index=row[1],
                content=row[2],
                title=row[3],
                doc_type=row[4],
                version=row[5],
                source_path=row[6],
                tenant_id=row[7],
                score=float(row[8])
            )
            for row in rows
        ]
    
    def _search_vector(self, 
                       query: str, 
                       tenant_id: Optional[str],
                       doc_type: Optional[str],
                       top_k: int = 20) -> List[SearchResult]:
        """
        Vector semantic search using pgvector cosine similarity.
        """
        if not self.embedder:
            raise ValueError("Embedder required for vector search")
        
        # Generate query embedding
        query_embedding = self.embedder.embed_query(query)
        
        # Build SQL query
        sql = """
            SELECT 
                document_id, chunk_index, content, title, doc_type,
                version, source_path, tenant_id,
                1 - (embedding <=> %s::vector) as similarity
            FROM document_embeddings
            WHERE 1=1
        """
        params = [query_embedding]
        
        if tenant_id:
            sql += " AND tenant_id = %s"
            params.append(tenant_id)
        
        if doc_type:
            sql += " AND doc_type = %s"
            params.append(doc_type)
        
        sql += " ORDER BY embedding <=> %s::vector LIMIT %s"
        params.extend([query_embedding, top_k])
        
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        
        return [
            SearchResult(
                document_id=row[0],
                chunk_index=row[1],
                content=row[2],
                title=row[3],
                doc_type=row[4],
                version=row[5],
                source_path=row[6],
                tenant_id=row[7],
                score=float(row[8])
            )
            for row in rows
        ]
    
    def _reciprocal_rank_fusion(self,
                                bm25_results: List[SearchResult],
                                vector_results: List[SearchResult],
                                k: int = 60,
                                bm25_weight: float = 0.5,
                                vector_weight: float = 0.5) -> List[SearchResult]:
        """
        Merge rankings using Reciprocal Rank Fusion (RRF).
        
        RRF formula: score = sum(weight / (k + rank))
        where k=60 is a constant, rank is position in result list
        
        Args:
            bm25_results: Results from BM25 search
            vector_results: Results from vector search
            k: RRF constant (default 60)
            bm25_weight: Weight for BM25 rankings
            vector_weight: Weight for vector rankings
        
        Returns:
            Fused results sorted by RRF score
        """
        # Build rank maps: (doc_id, chunk_idx) -> rank
        bm25_ranks = {
            (r.document_id, r.chunk_index): i + 1 
            for i, r in enumerate(bm25_results)
        }
        vector_ranks = {
            (r.document_id, r.chunk_index): i + 1 
            for i, r in enumerate(vector_results)
        }
        
        # Collect all unique results
        all_results = {}
        for r in bm25_results + vector_results:
            key = (r.document_id, r.chunk_index)
            if key not in all_results:
                all_results[key] = r
        
        # Calculate RRF scores
        rrf_scores = {}
        for key, result in all_results.items():
            score = 0.0
            
            # Add BM25 contribution
            if key in bm25_ranks:
                score += bm25_weight / (k + bm25_ranks[key])
            
            # Add vector contribution
            if key in vector_ranks:
                score += vector_weight / (k + vector_ranks[key])
            
            rrf_scores[key] = score
        
        # Sort by RRF score descending
        sorted_keys = sorted(rrf_scores.keys(), key=lambda k: rrf_scores[k], reverse=True)
        
        # Build final result list with RRF scores
        fused_results = []
        for key in sorted_keys:
            result = all_results[key]
            result.score = rrf_scores[key]  # Replace with RRF score
            fused_results.append(result)
        
        return fused_results
    
    def format_results_with_citations(self, results: List[SearchResult]) -> str:
        """
        Format search results with citations.
        
        Args:
            results: List of SearchResult objects
        
        Returns:
            Formatted string with results and citations
        """
        output = []
        
        for i, result in enumerate(results, 1):
            citation = Citation(
                title=result.title,
                doc_type=result.doc_type,
                version=result.version,
                chunk_index=result.chunk_index,
                source_path=result.source_path
            )
            
            output.append(f"Result {i} (score: {result.score:.4f})")
            output.append(citation.format(i))
            output.append(f"Content: {result.content[:200]}...")
            output.append("")
        
        return "\n".join(output)
    
    def close(self):
        """Close database connection."""
        self.conn.close()
