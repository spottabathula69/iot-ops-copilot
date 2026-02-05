"""
Generate embeddings for document chunks using OpenAI API.
"""

from openai import OpenAI
from typing import List
import os
import time

class DocumentEmbedder:
    """Generate embeddings using OpenAI text-embedding-3-small model."""
    
    def __init__(self, api_key: str = None):
        """
        Initialize OpenAI embedder.
        
        Args:
            api_key: OpenAI API key (or set OPENAI_API_KEY env var)
        """
        self.client = OpenAI(api_key=api_key or os.getenv('OPENAI_API_KEY'))
        self.model = "text-embedding-3-small"
        self.embedding_dim = 1536
    
    def embed_chunks(self, chunks: List[str], batch_size: int = 100) -> List[List[float]]:
        """
        Generate embeddings for a list of text chunks.
        
        Args:
            chunks: List of text strings
            batch_size: Max chunks per API call (OpenAI limit: 2048)
        
        Returns:
            List of embeddings (each is a list of 1536 floats)
        """
        all_embeddings = []
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            
            try:
                response = self.client.embeddings.create(
                    input=batch,
                    model=self.model
                )
                all_embeddings.extend([item.embedding for item in response.data])
                
                # Rate limiting: sleep briefly between batches
                if i + batch_size < len(chunks):
                    time.sleep(0.1)
                    
            except Exception as e:
                print(f"Error embedding batch {i//batch_size + 1}: {e}")
                raise
        
        return all_embeddings
    
    def embed_query(self, query: str) -> List[float]:
        """
        Generate embedding for a single query.
        
        Args:
            query: Search query string
        
        Returns:
            Embedding vector (1536 floats)
        """
        response = self.client.embeddings.create(
            input=[query],
            model=self.model
        )
        return response.data[0].embedding
    
    def get_embedding_dimension(self) -> int:
        """Get embedding dimension for this model."""
        return self.embedding_dim
