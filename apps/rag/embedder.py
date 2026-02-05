"""
Generate embeddings for document chunks.

Supports both local (sentence-transformers) and OpenAI models.
"""

from typing import List, Union
import os
import time


class DocumentEmbedder:
    """
    Generate embeddings using configurable backend.
    
    Supported models:
    - 'local': sentence-transformers/all-MiniLM-L6-v2 (384 dims, CPU-friendly, free)
    - 'openai': text-embedding-3-small (1536 dims, better quality, API cost)
    """
    
    def __init__(self, model: str = 'local', api_key: str = None):
        """
        Initialize embedder.
        
        Args:
            model: 'local' or 'openai'
            api_key: OpenAI API key (only needed for model='openai')
        """
        self.model_type = model
        
        if model == 'local':
            from sentence_transformers import SentenceTransformer
            print("Loading local embedding model (sentence-transformers/all-MiniLM-L6-v2)...")
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            self.embedding_dim = 384
            self.model_name = 'all-MiniLM-L6-v2'
            print(f"✅ Loaded local model ({self.embedding_dim} dimensions)")
            
        elif model == 'openai':
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key or os.getenv('OPENAI_API_KEY'))
            self.embedding_dim = 1536
            self.model_name = 'text-embedding-3-small'
            print(f"✅ Using OpenAI model ({self.embedding_dim} dimensions)")
            
        else:
            raise ValueError(f"Unsupported model: {model}. Use 'local' or 'openai'.")
    
    def embed_chunks(self, chunks: List[str], batch_size: int = 32) -> List[List[float]]:
        """
        Generate embeddings for a list of text chunks.
        
        Args:
            chunks: List of text strings
            batch_size: Batch size (32 for local, 100 for OpenAI)
        
        Returns:
            List of embeddings (each is a list of floats)
        """
        if self.model_type == 'local':
            return self._embed_local(chunks, batch_size)
        else:
            return self._embed_openai(chunks, batch_size)
    
    def _embed_local(self, chunks: List[str], batch_size: int) -> List[List[float]]:
        """Generate embeddings using local sentence-transformers model."""
        import numpy as np
        
        embeddings = self.model.encode(
            chunks,
            batch_size=batch_size,
            show_progress_bar=True,
            convert_to_numpy=True
        )
        
        # Convert numpy arrays to lists for pgvector
        return embeddings.tolist()
    
    def _embed_openai(self, chunks: List[str], batch_size: int = 100) -> List[List[float]]:
        """Generate embeddings using OpenAI API."""
        all_embeddings = []
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            
            try:
                response = self.client.embeddings.create(
                    input=batch,
                    model=self.model_name
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
            Embedding vector
        """
        if self.model_type == 'local':
            import numpy as np
            embedding = self.model.encode(query, convert_to_numpy=True)
            return embedding.tolist()
        else:
            response = self.client.embeddings.create(
                input=[query],
                model=self.model_name
            )
            return response.data[0].embedding
    
    def get_embedding_dimension(self) -> int:
        """Get embedding dimension for this model."""
        return self.embedding_dim
    
    def get_model_name(self) -> str:
        """Get model identifier."""
        return self.model_name

