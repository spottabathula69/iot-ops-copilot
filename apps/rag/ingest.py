"""
Document ingestion script for RAG pipeline.

Reads documents, chunks them, generates embeddings, and stores in pgvector.
"""

import os
import sys
import psycopg2
from typing import List, Dict
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from rag.chunker import DocumentChunker
from rag.embedder import DocumentEmbedder


class DocumentIngester:
    """Ingest documents into pgvector database."""
    
    def __init__(self, db_conn_string: str, embedding_model: str = 'local', api_key: str = None):
        """
        Initialize ingester.
        
        Args:
            db_conn_string: PostgreSQL connection string
            embedding_model: 'local' (default) or 'openai'
            api_key: OpenAI API key (only needed for model='openai')
        """
        self.conn = psycopg2.connect(db_conn_string)
        self.chunker = DocumentChunker(chunk_size=512, chunk_overlap=50)
        self.embedder = DocumentEmbedder(model=embedding_model, api_key=api_key)
        self.embedding_model = self.embedder.get_model_name()
    
    def ingest_document(self, file_path: str, metadata: Dict) -> int:
        """
        Ingest a single document.
        
        Args:
            file_path: Path to document file
            metadata: Document metadata (title, doc_type, tenant_id, version)
        
        Returns:
            Number of chunks ingested
        """
        print(f"Reading document: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Add source_path to metadata
        metadata['source_path'] = file_path
        
        # Calculate file hash for deduplication
        file_hash = self.chunker.calculate_file_hash(content)
        
        # Check if document already exists
        if self._document_exists(file_hash):
            print(f"Document already ingested (hash: {file_hash[:16]}...)")
            return 0
        
        # Chunk document
        print(f"Chunking document (target size: 512 chars)...")
        chunks = self.chunker.chunk_document(content, metadata)
        print(f"Created {len(chunks)} chunks")
        
        # Generate embeddings
        print(f"Generating embeddings with {self.embedder.model_type} model ({self.embedding_model})...")
        chunk_texts = [chunk['content'] for chunk in chunks]
        embeddings = self.embedder.embed_chunks(chunk_texts)
        print(f"Generated {len(embeddings)} embeddings")
        
        # Insert into database
        print(f"Inserting into pgvector...")
        self._insert_document_metadata(
            document_id=chunks[0]['document_id'],
            metadata=metadata,
            file_hash=file_hash,
            chunk_count=len(chunks),
            total_size=len(content)
        )
        
        self._insert_embeddings(chunks, embeddings)
        
        print(f"✅ Successfully ingested {len(chunks)} chunks")
        return len(chunks)
    
    def _document_exists(self, file_hash: str) -> bool:
        """Check if document with this hash already exists."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM documents WHERE file_hash = %s LIMIT 1",
                (file_hash,)
            )
            return cur.fetchone() is not None
    
    def _insert_document_metadata(self, document_id: str, metadata: Dict, 
                                   file_hash: str, chunk_count: int, total_size: int):
        """Insert document metadata into documents table."""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO documents (
                    document_id, tenant_id, doc_type, title, source_path,
                    file_hash, version, chunk_count, total_size_bytes,
                    embedding_model, last_updated
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (document_id) DO UPDATE
                SET chunk_count = EXCLUDED.chunk_count,
                    last_updated = EXCLUDED.last_updated
            """, (
                document_id,
                metadata['tenant_id'],
                metadata['doc_type'],
                metadata['title'],
                metadata['source_path'],
                file_hash,
                metadata.get('version', '1.0'),
                chunk_count,
                total_size,
                self.embedding_model,
                metadata.get('last_updated', datetime.utcnow())
            ))
        self.conn.commit()
    
    def _insert_embeddings(self, chunks: List[Dict], embeddings: List[List[float]]):
        """Insert chunk embeddings into document_embeddings table."""
        with self.conn.cursor() as cur:
            for chunk, embedding in zip(chunks, embeddings):
                cur.execute("""
                    INSERT INTO document_embeddings (
                        document_id, tenant_id, chunk_index, doc_type, title,
                        source_path, version, last_updated, content, chunk_size, embedding
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (document_id, chunk_index) DO UPDATE
                    SET content = EXCLUDED.content,
                        embedding = EXCLUDED.embedding,
                        last_updated = EXCLUDED.last_updated
                """, (
                    chunk['document_id'],
                    chunk['tenant_id'],
                    chunk['chunk_index'],
                    chunk['doc_type'],
                    chunk['title'],
                    chunk['source_path'],
                    chunk['version'],
                    chunk['last_updated'],
                    chunk['content'],
                    chunk['chunk_size'],
                    embedding  # pgvector will handle list → vector conversion
                ))
        self.conn.commit()
    
    def search_similar(self, query: str, tenant_id: str = None, 
                      doc_type: str = None, top_k: int = 5) -> List[Dict]:
        """
        Search for similar document chunks.
        
        Args:
            query: Search query
            tenant_id: Filter by tenant (optional)
            doc_type: Filter by document type (optional)
            top_k: Number of results to return
        
        Returns:
            List of dicts with chunk content, metadata, and similarity score
        """
        print(f"Searching for: '{query}'")
        
        # Generate query embedding
        query_embedding = self.embedder.embed_query(query)
        
        # Build SQL query with optional filters
        sql = """
            SELECT 
                document_id, chunk_index, title, doc_type, content,
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
        
        # Execute search
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            results = cur.fetchall()
        
        # Format results
        return [
            {
                'document_id': row[0],
                'chunk_index': row[1],
                'title': row[2],
                'doc_type': row[3],
                'content': row[4],
                'similarity': float(row[5])
            }
            for row in results
        ]
    
    def get_stats(self) -> Dict:
        """Get ingestion statistics."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    COUNT(DISTINCT document_id) as document_count,
                    COUNT(*) as chunk_count,
                    AVG(chunk_size) as avg_chunk_size
                FROM document_embeddings
            """)
            row = cur.fetchone()
            
            cur.execute("SELECT COUNT(DISTINCT tenant_id) FROM document_embeddings")
            tenant_count = cur.fetchone()[0]
        
        return {
            'documents': row[0] if row else 0,
            'chunks': row[1] if row else 0,
            'avg_chunk_size': int(row[2]) if row and row[2] else 0,
            'tenants': tenant_count
        }
    
    def close(self):
        """Close database connection."""
        self.conn.close()


def main():
    """Main ingestion script."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Ingest documents into RAG database')
    parser.add_argument('--file', required=True, help='Path to document file')
    parser.add_argument('--title', required=True, help='Document title')
    parser.add_argument('--doc-type', default='manual', 
                       choices=['manual', 'runbook', 'kb_article', 'ADR'],
                       help='Document type')
    parser.add_argument('--tenant-id', required=True, help='Customer/tenant ID')
    parser.add_argument('--version', default='1.0', help='Document version')
    parser.add_argument('--model', default='local', choices=['local', 'openai'],
                       help='Embedding model: local (sentence-transformers) or openai (default: local)')
    parser.add_argument('--db-host', default='localhost', help='Database host')
    parser.add_argument('--db-port', default='5432', help='Database port')
    parser.add_argument('--db-name', default='iot_ops', help='Database name')
    parser.add_argument('--db-user', default='postgres', help='Database user')
    parser.add_argument('--db-password', default='postgres', help='Database password')
    
    args = parser.parse_args()
    
    # Build connection string
    db_conn = f"host={args.db_host} port={args.db_port} dbname={args.db_name} " \
              f"user={args.db_user} password={args.db_password}"
    
    # Create ingester with configured model
    ingester = DocumentIngester(db_conn, embedding_model=args.model)
    
    try:
        # Ingest document
        chunk_count = ingester.ingest_document(
            file_path=args.file,
            metadata={
                'title': args.title,
                'doc_type': args.doc_type,
                'tenant_id': args.tenant_id,
                'version': args.version
            }
        )
        
        # Show stats
        stats = ingester.get_stats()
        print(f"\n📊 Database Stats:")
        print(f"  Total documents: {stats['documents']}")
        print(f"  Total chunks: {stats['chunks']}")
        print(f"  Average chunk size: {stats['avg_chunk_size']} chars")
        print(f"  Tenants: {stats['tenants']}")
        
    finally:
        ingester.close()


if __name__ == '__main__':
    main()
