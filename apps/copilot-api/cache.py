"""
Response caching for copilot API.

Simple in-memory cache with TTL for faster repeated queries.
"""

import time
import hashlib
from typing import Optional, Dict, Any


class ResponseCache:
    """In-memory cache for LLM responses with TTL."""
    
    def __init__(self, ttl_seconds: int = 3600):
        """
        Initialize cache.
        
        Args:
            ttl_seconds: Time-to-live for cached entries (default 1 hour)
        """
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl = ttl_seconds
    
    def _generate_key(self, query: str, tenant_id: str, **kwargs) -> str:
        """
        Generate cache key from query parameters.
        
        Args:
            query: User query
            tenant_id: Tenant ID
            **kwargs: Additional parameters (e.g., doc_types, max_context)
        
        Returns:
            SHA256 hash of normalized parameters
        """
        # Normalize parameters for consistent hashing
        params = f"{query}:{tenant_id}:{sorted(kwargs.items())}"
        return hashlib.sha256(params.encode()).hexdigest()
    
    def get(self, query: str, tenant_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Get cached response if available and not expired.
        
        Args:
            query: User query
            tenant_id: Tenant ID
            **kwargs: Additional query parameters
        
        Returns:
            Cached response or None if not found/expired
        """
        key = self._generate_key(query, tenant_id, **kwargs)
        entry = self.cache.get(key)
        
        if not entry:
            return None
        
        # Check if expired
        if time.time() - entry['timestamp'] > self.ttl:
            del self.cache[key]
            return None
        
        return entry['response']
    
    def set(self, query: str, tenant_id: str, response: Dict[str, Any], **kwargs):
        """
        Cache a response.
        
        Args:
            query: User query
            tenant_id: Tenant ID
            response: Response to cache
            **kwargs: Additional query parameters
        """
        key = self._generate_key(query, tenant_id, **kwargs)
        self.cache[key] = {
            'response': response,
            'timestamp': time.time()
        }
    
    def clear(self):
        """Clear all cached entries."""
        self.cache.clear()
    
    def stats(self) -> Dict[str, int]:
        """
        Get cache statistics.
        
        Returns:
            Dict with total entries and expired entries
        """
        now = time.time()
        expired = sum(1 for entry in self.cache.values() 
                     if now - entry['timestamp'] > self.ttl)
        
        return {
            'total_entries': len(self.cache),
            'expired_entries': expired,
            'active_entries': len(self.cache) - expired
        }
