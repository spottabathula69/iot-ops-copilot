"""
Local LLM integration using llama-cpp-python.

Supports CPU inference with quantized models (no GPU required).
"""

from typing import Optional, Dict, Any
import os


class LlamaModel:
    """
    Local Llama model wrapper using llama-cpp-python.
    
    Supports CPU inference with 4-bit quantized models.
    """
    
    def __init__(self, 
                 model_path: str = None,
                 n_ctx: int = 4096,
                 n_threads: int = 8,
                 temperature: float = 0.7,
                 max_tokens: int = 256):
        """
        Initialize Llama model.
        
        Args:
            model_path: Path to GGUF model file
            n_ctx: Context window size
            n_threads: Number of CPU threads
            temperature: Sampling temperature (0-1)
            max_tokens: Max tokens to generate
        """
        try:
            from llama_cpp import Llama
        except ImportError:
            raise ImportError(
                "llama-cpp-python not installed. "
                "Install with: pip install llama-cpp-python"
            )
        
        self.model_path = model_path or os.getenv('LLAMA_MODEL_PATH')
        if not self.model_path:
            raise ValueError(
                "Model path required. Set LLAMA_MODEL_PATH env var or pass model_path.\n"
                "Download model: https://huggingface.co/TheBloke/Llama-2-7B-Chat-GGUF"
            )
        
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Model not found: {self.model_path}")
        
        print(f"Loading Llama model from {self.model_path}...")
        print(f"  Context window: {n_ctx}")
        print(f"  CPU threads: {n_threads}")
        
        self.llm = Llama(
            model_path=self.model_path,
            n_ctx=n_ctx,
            n_threads=n_threads,
            n_gpu_layers=0,  # CPU-only
            verbose=False
        )
        
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        print(f"✅ Llama model loaded successfully")
    
    def generate(self, 
                 prompt: str,
                 temperature: Optional[float] = None,
                 max_tokens: Optional[int] = None,
                 stop: Optional[list] = None) -> str:
        """
        Generate text completion.
        
        Args:
            prompt: Input prompt
            temperature: Sampling temperature (overrides default)
            max_tokens: Max tokens (overrides default)
            stop: Stop sequences
        
        Returns:
            Generated text
        """
        response = self.llm(
            prompt,
            max_tokens=max_tokens or self.max_tokens,
            temperature=temperature or self.temperature,
            top_p=0.9,
            stop=stop or ["\n\nUser:", "\n\nHuman:", "###"],
            echo=False
        )
        
        return response['choices'][0]['text'].strip()
    
    def generate_with_metadata(self,
                               prompt: str,
                               **kwargs) -> Dict[str, Any]:
        """
        Generate with full response metadata.
        
        Returns:
            Dict with 'text', 'tokens_generated', 'finish_reason'
        """
        response = self.llm(prompt, **kwargs)
        
        return {
            'text': response['choices'][0]['text'].strip(),
            'tokens_generated': response['usage']['completion_tokens'],
            'finish_reason': response['choices'][0]['finish_reason']
        }


class PromptTemplate:
    """Prompt templates for RAG-grounded Q&A."""
    
    @staticmethod
    def rag_qa(query: str, context: list, citations: list) -> str:
        """
        Build RAG-grounded Q&A prompt.
        
        Args:
            query: User question
            context: List of relevant text chunks
            citations: List of citation strings
        
        Returns:
            Formatted prompt
        """
        context_str = ""
        for i, (chunk, citation) in enumerate(zip(context, citations), 1):
            context_str += f"[{i}] {citation}\n{chunk}\n\n"
        
        prompt = f"""You are an IoT operations assistant helping troubleshoot industrial equipment.

Answer the user's question using ONLY the provided context from equipment manuals and runbooks.

Rules:
- If the context doesn't contain the answer, say "I don't have enough information to answer that question."
- Always cite your sources using [1], [2], etc.
- Be concise and practical
- Focus on actionable steps when applicable

Context:
{context_str}

Question: {query}

Answer:"""
        
        return prompt
    
    @staticmethod
    def troubleshooting(error_code: str, context: list) -> str:
        """Build troubleshooting guide prompt."""
        context_str = "\n\n".join(context)
        
        prompt = f"""You are an equipment troubleshooting assistant.

Create a step-by-step troubleshooting guide for the error code below using the provided manual context.

Error Code: {error_code}

Context from manual:
{context_str}

Provide:
1. A brief explanation of what this error means
2. Step-by-step troubleshooting actions (numbered)
3. Tools or parts needed (if any)
4. Estimated time to resolve

Troubleshooting Guide:"""
        
        return prompt


# Mock model for testing without actual model file
class MockLlamaModel:
    """Mock LLM for testing without model file."""
    
    def __init__(self, *args, **kwargs):
        print("✅ Mock Llama model loaded (testing mode)")
    
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate mock response."""
        if "VIB_HIGH_001" in prompt or "vibration" in prompt.lower():
            return """High vibration alarm (VIB_HIGH_001) indicates excessive machine vibration above the 2.0 mm/s threshold [1].

To resolve this issue:
1. Press E-Stop to halt machining immediately [1]
2. Inspect the cutting tool for wear, chips, or damage [1]
3. Check spindle bearings for unusual noise or play [2]
4. Reduce spindle speed by 20% and retry [2]

If vibration persists after these steps, contact maintenance as spindle bearing replacement may be required [1]."""
        
        return "Based on the provided context, I can help with that question. [Mock response]"
    
    def generate_with_metadata(self, prompt: str, **kwargs):
        text = self.generate(prompt, **kwargs)
        return {
            'text': text,
            'tokens_generated': len(text.split()),
            'finish_reason': 'stop'
        }
