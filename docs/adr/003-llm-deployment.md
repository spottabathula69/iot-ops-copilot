# ADR-003: LLM Deployment Strategy

**Status**: Accepted

**Date**: 2026-02-04

**Deciders**: Platform Team

**Technical Story**: Need to choose LLM deployment approach that balances cost, development speed, and production realism for the Copilot service.

## Context and Problem Statement

The Copilot API requires LLM inference for Q&A, insights, and troubleshooting features. Key considerations:

1. **GPU Access**: Local development uses kind (limited GPU support), production will use EKS
2. **Cost**: Budget-conscious during development, need to optimize expenses
3. **Flexibility**: Should support multiple LLM providers (OpenAI, local models, AWS Bedrock)
4. **Development Speed**: Fast iteration during Phase 5 implementation
5. **Portfolio Value**: Demonstrate both managed services AND self-hosted ML capabilities

## Decision Drivers

- **Cost Efficiency**: Minimize expenses during development (~6-8 weeks)
- **Architectural Flexibility**: Easy provider switching without code changes
- **GPU Utilization**: Use available 12GB GPU on Windows 11 machine for demos
- **Production Realism**: Match real-world patterns (separation of concerns)
- **Development Velocity**: Don't block on complex GPU passthrough in kind

## Considered Options

- Option 1: **LLM in Kubernetes (kind/EKS with GPU nodes)**
- Option 2: **Separate LLM Service with Multiple Providers** (CHOSEN)
- Option 3: **Only OpenAI API**

## Decision Outcome

**Chosen option**: "Option 2: Separate LLM Service with Multiple Providers"

Deploy LLM inference as a **separate service** outside the Kubernetes cluster, accessed via HTTP. Support multiple providers through configuration:

1. **OpenAI API** (development, fast iteration)
2. **Ollama (local Llama 3.1)** (demos, cost-free)
3. **AWS Bedrock** (AWS production)
4. **Vertex AI** (GCP production, Gemini models)

### Architecture

```
┌─────────────────────────────────────────┐
│  Kubernetes (kind/EKS)                  │
│  ┌───────────────────────────────────┐  │
│  │   Copilot API (FastAPI)           │  │
│  │   - LLM Provider Factory          │  │
│  │   - Configurable via ENV          │  │
│  └───────────────┬───────────────────┘  │
└──────────────────┼──────────────────────┘
                   │ HTTP
        ┌──────────┴──────────┬──────────────┬──────────────┐
        │                     │              │              │
        ▼                     ▼              ▼              ▼
┌───────────────┐   ┌──────────────┐   ┌──────────┐   ┌──────────┐
│   OpenAI API  │   │   Ollama     │   │ Bedrock  │   │ Vertex AI│
│   (Cloud)     │   │ (Windows GPU)│   │  (AWS)   │   │  (GCP)   │
└───────────────┘   └──────────────┘   └──────────┘   └──────────┘
```

### Configuration-Based Switching

```yaml
# config/llm.yaml
llm:
  provider: "ollama"  # openai | ollama | bedrock | vertexai
  
  openai:
    api_key: ${OPENAI_API_KEY}
    model: "gpt-4o-mini"
    base_url: "https://api.openai.com/v1"
  
  ollama:
    base_url: "http://192.168.1.100:11434"  # Windows GPU machine
    model: "llama3.1:8b"
  
  bedrock:
    region: "us-west-2"
    model_id: "anthropic.claude-3-sonnet"
  
  vertexai:
    project_id: ${GCP_PROJECT_ID}
    location: "us-central1"
    model: "gemini-1.5-pro"  # or gemini-1.5-flash
```

**Simple switch**: Change `llm.provider` in config or set `LLM_PROVIDER` environment variable.

### Consequences

**Good**:
- No GPU passthrough complexity in kind
- Use 12GB Windows GPU for cost-free inference (Ollama)
- Pay-per-use with OpenAI during development ($10-20/month)
- Easy A/B testing between providers (quality, latency, cost)
- Production-realistic (matches how companies deploy: separated concerns)
- Portfolio demonstrates both managed services AND self-hosted ML

**Bad**:
- Network dependency when using remote LLM (Ollama on Windows)
- Need to manage separate LLM service lifecycle
- Slightly more complex configuration

**Neutral**:
- OpenAI-compatible API standard makes switching seamless
- All providers support streaming responses

### Confirmation

Success criteria:
- Single config change switches between OpenAI and Ollama
- Latency benchmarks documented for each provider
- Cost comparison documented ($/1M tokens)
- Demo showcases local Llama model running on GPU

## Pros and Cons of the Options

### Option 1: LLM in Kubernetes with GPU Nodes

**Description**: Deploy LLM inference pods on GPU-enabled Kubernetes nodes.

**Pros**:
- Single cluster for all services
- Native K8s scaling (HPA with GPU metrics)
- Simplest networking (no external dependencies)

**Cons**:
- kind GPU support is experimental (nvidia-docker, device plugins)
- Requires GPU nodes in EKS (expensive: g4dn.xlarge ~$0.50/hr)
- Complex setup during development phase
- Can't use Windows 12GB GPU from Linux kind cluster
- Blocks development while troubleshooting GPU passthrough

**Estimated Cost**: ~$360/month (EKS GPU node running 24/7)

### Option 2: Separate LLM Service (CHOSEN)

**Description**: LLM as external HTTP service, configurable provider.

**Pros**:
- No kind GPU complexity
- Uses Windows 12GB GPU via Ollama (free!)
- OpenAI API for fast development ($10-20/month)
- Easy provider switching (config change)
- Matches production patterns (Bedrock, Azure OpenAI)
- Demonstrates architectural maturity

**Cons**:
- Need to manage LLM service separately
- Network latency between services (minor, <10ms local)

**Estimated Cost**: $10-20/month (dev phase), $0 (demo with Ollama)

### Option 3: Only OpenAI API

**Description**: Use OpenAI API exclusively, no self-hosted option.

**Pros**:
- Simplest implementation
- Best quality (GPT-4)
- Zero infrastructure management

**Cons**:
- Ongoing cost (~$50-100/month with moderate usage)
- No demonstration of self-hosted ML capability
- Vendor lock-in for portfolio project
- Less impressive ("just called an API")

**Estimated Cost**: $50-100/month (ongoing)

## Implementation Phases

### Phase 5: Initial Copilot Implementation
- Deploy with **OpenAI API** (fast development)
- Abstract LLM calls behind `LLMService` interface

### Phase 5.5: Local GPU Demo
- Install **Ollama on Windows 11**
- Pull **Llama 3.1 8B** (8-bit quantization)
- Update config to support provider switching
- Benchmark: OpenAI vs Ollama (latency, quality, cost)

### Phase 7: Production Simulation (Cloud)
- Option A: **AWS Bedrock** (AWS managed)
- Option B: **Vertex AI** (GCP managed, Gemini models)
- Option C: **vLLM on GPU instances** (self-managed)

## Technical Implementation

### LLM Provider Interface

```python
# app/services/llm/base.py
from abc import ABC, abstractmethod

class LLMProvider(ABC):
    @abstractmethod
    def generate(self, messages: list[dict], **kwargs) -> str:
        pass
    
    @abstractmethod
    def stream(self, messages: list[dict], **kwargs):
        pass

# app/services/llm/openai_provider.py
class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model

# app/services/llm/ollama_provider.py
class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str, model: str):
        self.client = openai.OpenAI(
            base_url=f"{base_url}/v1",
            api_key="not-needed"
        )
        self.model = model

# app/services/llm/vertexai_provider.py
class VertexAIProvider(LLMProvider):
    def __init__(self, project_id: str, location: str, model: str):
        from vertexai.generative_models import GenerativeModel
        import vertexai
        vertexai.init(project=project_id, location=location)
        self.model = GenerativeModel(model)

# app/services/llm/factory.py
def create_llm_provider(config: dict) -> LLMProvider:
    provider = config.get("provider", "openai")
    
    if provider == "openai":
        return OpenAIProvider(...)
    elif provider == "ollama":
        return OllamaProvider(...)
    elif provider == "bedrock":
        return BedrockProvider(...)
    elif provider == "vertexai":
        return VertexAIProvider(...)
```

### Environment-Based Configuration

```bash
# .env.local (development with OpenAI)
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# .env.demo (demo with local Llama)
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://192.168.1.100:11434
OLLAMA_MODEL=llama3.1:8b

# .env.prod-aws (production on AWS)
LLM_PROVIDER=bedrock
AWS_REGION=us-west-2
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet

# .env.prod-gcp (production on GCP)
LLM_PROVIDER=vertexai
GCP_PROJECT_ID=your-project-id
VERTEXAI_LOCATION=us-central1
VERTEXAI_MODEL=gemini-1.5-pro
```

## Benchmarking Plan

Document performance comparison in `docs/BENCHMARKS.md`:

| Provider | Model | p50 Latency | p95 Latency | Cost/1M Tokens | Quality Score |
|----------|-------|-------------|-------------|----------------|---------------|
| OpenAI | gpt-4o-mini | 800ms | 1.5s | $0.15 | 9/10 |
| Ollama (Local) | llama3.1:8b | 600ms | 1.2s | $0 | 7.5/10 |
| Bedrock (AWS) | claude-3-sonnet | 1.2s | 2.5s | $3.00 | 9.5/10 |
| Vertex AI (GCP) | gemini-1.5-pro | 900ms | 1.8s | $1.25 | 9/10 |
| Vertex AI (GCP) | gemini-1.5-flash | 400ms | 800ms | $0.075 | 8/10 |

## More Information

- Ollama documentation: https://ollama.ai/
- OpenAI API pricing: https://openai.com/pricing
- AWS Bedrock: https://aws.amazon.com/bedrock/
- Related ADRs:
  - ADR-001: Local Kubernetes (kind)
  - ADR-005: RAG Architecture (future)
