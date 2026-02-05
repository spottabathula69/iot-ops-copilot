"""
Document chunking service for RAG ingestion.
Splits documents into semantic chunks for embedding.
"""

from typing import List, Dict
from langchain.text_splitter import RecursiveCharacterTextSplitter
import hashlib
from datetime import datetime

class DocumentChunker:
    """Chunk documents into fixed-size segments with overlap."""
    
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        """
        Initialize chunker.
        
        Args:
            chunk_size: Target size of each chunk in characters
            chunk_overlap: Number of characters to overlap between chunks
        """
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )
    
    def chunk_document(self, content: str, metadata: Dict) -> List[Dict]:
        """
        Split document into chunks with metadata.
        
        Args:
            content: Document text content
            metadata: Document metadata dict with keys:
                - title: Document title
                - doc_type: Type (manual, runbook, kb_article, ADR)
                - tenant_id: Customer ID for multi-tenancy
                - source_path: File path or URL
                - version: Document version (optional)
        
        Returns:
            List of chunk dicts, each containing:
                - document_id: Unique doc ID (hash of source_path + version)
                - chunk_index: Index of chunk in document
                - content: Chunk text
                - chunk_size: Length of chunk
                - All metadata fields
                - last_updated: Timestamp
        """
        chunks = self.splitter.split_text(content)
        
        document_id = self._generate_doc_id(
            metadata['source_path'],
            metadata.get('version', '1.0')
        )
        
        return [
            {
                'document_id': document_id,
                'chunk_index': idx,
                'content': chunk,
                'chunk_size': len(chunk),
                'title': metadata['title'],
                'doc_type': metadata['doc_type'],
                'tenant_id': metadata['tenant_id'],
                'source_path': metadata['source_path'],
                'version': metadata.get('version', '1.0'),
                'last_updated': datetime.utcnow(),
            }
            for idx, chunk in enumerate(chunks)
        ]
    
    def _generate_doc_id(self, source_path: str, version: str) -> str:
        """
        Generate unique document ID from path + version.
        
        Args:
            source_path: File path or URL
            version: Document version
        
        Returns:
            16-character hex document ID
        """
        return hashlib.sha256(
            f"{source_path}:{version}".encode()
        ).hexdigest()[:16]
    
    def calculate_file_hash(self, content: str) -> str:
        """
        Calculate SHA256 hash of file content for deduplication.
        
        Args:
            content: File content
        
        Returns:
            64-character hex hash
        """
        return hashlib.sha256(content.encode()).hexdigest()
