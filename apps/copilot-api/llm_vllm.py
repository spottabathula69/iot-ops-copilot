"""
vLLM integration for fast GPU inference.

Uses HuggingFace models with vLLM's optimized inference engine.
Much faster than llama-cpp-python (~10-20x speedup).
"""

from typing import Optional, List
import os


class VLLMModel:
    """
    vLLM model wrapper for fast inference.
    
    Automatically handles GPU offloading and optimized batching.
    """
    
    def __init__(self,
                 model_name: str = "meta-llama/Llama-2-7b-chat-hf",
                 tensor_parallel_size: int = 1,
                 max_model_len: int = 4096,
                 temperature: float = 0.7,
                 max_tokens: int = 256):
        """
        Initialize vLLM model.
        
        Args:
            model_name: HuggingFace model name or local path
            tensor_parallel_size: Number of GPUs to use (1 for single GPU)
            max_model_len: Maximum sequence length
            temperature: Sampling temperature
            max_tokens: Max tokens to generate
        """
        try:
            from vllm import LLM, SamplingParams
        except ImportError:
            raise ImportError(
                "vLLM not installed. "
                "Install with: pip install vllm"
            )
        
        self.model_name = model_name or os.getenv('VLLM_MODEL_NAME', 'meta-llama/Llama-2-7b-chat-hf')
        
        print(f"🚀 Loading vLLM model: {self.model_name}")
        print(f"  Max sequence length: {max_model_len}")
        print(f"  Tensor parallel: {tensor_parallel_size}")
        
        # Initialize vLLM engine
        self.llm = LLM(
            model=self.model_name,
            tensor_parallel_size=tensor_parallel_size,
            max_model_len=max_model_len,
            gpu_memory_utilization=0.9,  # Use 90% of available GPU memory
            trust_remote_code=True
        )
        
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        print(f"✅ vLLM model loaded successfully")
    
    def generate(self,
                 prompt: str,
                 temperature: Optional[float] = None,
                 max_tokens: Optional[int] = None,
                 stop: Optional[List[str]] = None) -> str:
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
        from vllm import SamplingParams
        
        sampling_params = SamplingParams(
            temperature=temperature or self.temperature,
            top_p=0.9,
            max_tokens=max_tokens or self.max_tokens,
            stop=stop or ["</s>", "[/INST]", "\n\nUser:", "\n\nHuman:"]
        )
        
        outputs = self.llm.generate([prompt], sampling_params)
        
        return outputs[0].outputs[0].text.strip()
    
    def generate_with_metadata(self, prompt: str, **kwargs):
        """
        Generate with full response metadata.
        
        Returns:
            Dict with 'text', 'tokens_generated', 'finish_reason'
        """
        from vllm import SamplingParams
        
        sampling_params = SamplingParams(
            temperature=kwargs.get('temperature', self.temperature),
            max_tokens=kwargs.get('max_tokens', self.max_tokens),
        )
        
        outputs = self.llm.generate([prompt], sampling_params)
        output = outputs[0].outputs[0]
        
        return {
            'text': output.text.strip(),
            'tokens_generated': len(output.token_ids),
            'finish_reason': output.finish_reason
        }


class PromptTemplateVLLM:
    """Prompt templates for vLLM with Llama 2 chat format."""
    
    @staticmethod
    def rag_qa(query: str, context: list, citations: list) -> str:
        """
       Build RAG-grounded Q&A prompt in Llama 2 chat format.
        
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
        
        # Llama 2 chat format
        prompt = f"""<s>[INST] <<SYS>>
You are an IoT operations assistant helping troubleshoot industrial equipment.
Answer the user's question using ONLY the provided context from equipment manuals and runbooks.

Rules:
- If the context doesn't contain the answer, say "I don't have enough information to answer that question."
- Always cite your sources using [1], [2], etc.
- Be concise and practical
- Focus on actionable steps when applicable
<</SYS>>

Context:
{context_str}

Question: {query} [/INST]"""
        
        return prompt
    
    @staticmethod
    def troubleshooting(error_code: str, context: list) -> str:
        """Build troubleshooting guide prompt."""
        context_str = "\n\n".join(context)
        
        prompt = f"""<s>[INST] <<SYS>>
You are an equipment troubleshooting assistant.
Create a step-by-step troubleshooting guide for the error code below using the provided manual context.
<</SYS>>

Error Code: {error_code}

Context from manual:
{context_str}

Provide:
1. A brief explanation of what this error means
2. Step-by-step troubleshooting actions (numbered)
3. Tools or parts needed (if any)
4. Estimated time to resolve [/INST]"""
        
        return prompt


# Mock model for testing
class MockVLLMModel:
    """Mock vLLM for testing without model download."""
    
    def __init__(self, *args, **kwargs):
        print("✅ Mock vLLM model loaded (testing mode)")
    
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
        
        return "Based on the provided context, I can help with that question. [Mock vLLM response]"
    
    def generate_with_metadata(self, prompt: str, **kwargs):
        """Generate with metadata."""
        text = self.generate(prompt, **kwargs)
        return {
            'text': text,
            'tokens_generated': len(text.split()),
            'finish_reason': 'stop'
        }
