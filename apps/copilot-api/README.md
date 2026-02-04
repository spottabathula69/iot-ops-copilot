# Copilot API Setup Guide (Phase 5)

## LLM Provider Configuration

The Copilot API supports **four LLM providers** that can be switched with a simple configuration change:

1. **OpenAI API** - For development and production
2. **Ollama (Local Llama)** - For demos and cost-free inference
3. **AWS Bedrock** - For AWS production deployments
4. **Vertex AI** - For GCP production deployments (Gemini models)

---

## Quick Start

### Option 1: OpenAI API (Recommended for Development)

**Prerequisites**: OpenAI API key

**Setup**:
```bash
# Copy example environment file
cp .env.example .env

# Edit .env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o-mini

# Run
docker-compose up copilot-api
```

**Cost**: ~$0.15 per 1M tokens (~$10-20/month during development)

---

### Option 2: Ollama (Local Llama on GPU)

**Prerequisites**: 
- Windows 11 machine with 12GB GPU
- Ollama installed

**Setup Ollama (Windows 11)**:
```powershell
# Install Ollama
winget install Ollama.Ollama

# Pull Llama 3.1 8B (8-bit quantization, ~5GB VRAM)
ollama pull llama3.1:8b

# Start server (auto-detects GPU)
ollama serve
# Listens on http://localhost:11434
```

**Configure Copilot API (Linux laptop)**:
```bash
# Edit .env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://192.168.1.100:11434  # Your Windows machine IP
OLLAMA_MODEL=llama3.1:8b

# Run
docker-compose up copilot-api
```

**Verify GPU Usage** (on Windows):
```powershell
# Check GPU utilization
nvidia-smi

# Test Ollama API
curl http://localhost:11434/v1/chat/completions `
  -H "Content-Type: application/json" `
  -d '{"model": "llama3.1:8b", "messages": [{"role": "user", "content": "Hello!"}]}'
```

**Cost**: $0 (free!)

---

### Option 3: AWS Bedrock (AWS Production)

**Prerequisites**: AWS account with Bedrock access

**Setup**:
```bash
# Edit .env
LLM_PROVIDER=bedrock
AWS_REGION=us-west-2
BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0

# Ensure AWS credentials are configured
aws configure

# Run
docker-compose up copilot-api
```

**Cost**: ~$3.00 per 1M tokens (Claude 3 Sonnet)

---

### Option 4: Vertex AI (GCP Production)

**Prerequisites**: GCP account with Vertex AI API enabled

**Setup**:
```bash
# Edit .env
LLM_PROVIDER=vertexai
GCP_PROJECT_ID=your-gcp-project-id
VERTEXAI_LOCATION=us-central1
VERTEXAI_MODEL=gemini-1.5-pro  # or gemini-1.5-flash for faster/cheaper

# Authenticate with GCP
gcloud auth application-default login

# Run
docker-compose up copilot-api
```

**Cost**: 
- Gemini 1.5 Pro: ~$1.25 per 1M tokens
- Gemini 1.5 Flash: ~$0.075 per 1M tokens (8x cheaper!)

---

## Switching Between Providers

**Easy as changing one line in `.env`**:

```bash
# Use OpenAI
LLM_PROVIDER=openai

# Use Local Llama
LLM_PROVIDER=ollama

# Use AWS Bedrock
LLM_PROVIDER=bedrock

# Use GCP Vertex AI
LLM_PROVIDER=vertexai
```

No code changes required! Restart the service:
```bash
docker-compose restart copilot-api
```

---

## Testing Different Providers

### Benchmark Script

```bash
# Run benchmark comparing all providers
python scripts/benchmark_llm.py

# Output:
# Provider        | p50 Latency | p95 Latency | Cost/1M Tokens
# ----------------|-------------|-------------|----------------
# OpenAI          | 800ms       | 1.5s        | $0.15
# Ollama (Local)  | 600ms       | 1.2s        | $0.00
# Bedrock (AWS)   | 1.2s        | 2.5s        | $3.00
# Vertex AI (Pro) | 900ms       | 1.8s        | $1.25
# Vertex AI (Flash)| 400ms      | 800ms       | $0.075
```

### Quality Comparison

```bash
# Run quality eval on test set
python scripts/eval_llm_quality.py

# Compares citation accuracy, answer relevance, hallucination rate
```

---

## Troubleshooting

### Ollama Connection Issues

**Symptom**: `Connection refused to Ollama`

**Fix**:
```bash
# 1. Verify Ollama is running (on Windows)
curl http://localhost:11434/api/version

# 2. Check firewall allows port 11434

# 3. Verify IP address
# On Windows: ipconfig
# Update OLLAMA_BASE_URL in .env to correct IP
```

### Model Not Found

**Symptom**: `Model llama3.1:8b not found`

**Fix**:
```powershell
# On Windows, pull the model
ollama pull llama3.1:8b

# List available models
ollama list
```

### GPU Not Used by Ollama

**Symptom**: Slow inference, nvidia-smi shows 0% usage

**Fix**:
```powershell
# Ensure CUDA is installed
nvidia-smi

# Reinstall Ollama (should auto-detect CUDA)
winget uninstall Ollama.Ollama
winget install Ollama.Ollama

# Verify GPU detection
ollama run llama3.1:8b "Test prompt"
# Check nvidia-smi during inference
```

---

## Production Recommendations

| Environment | Recommended Provider | Rationale |
|-------------|---------------------|-----------|
| **Local Development** | OpenAI (gpt-4o-mini) | Fast iteration, best quality |
| **Demos/Portfolio** | Ollama (llama3.1:8b) | Free, impressive GPU usage |
| **Staging** | Vertex AI (Flash) or OpenAI | Cost-effective, managed |
| **Production (AWS)** | Bedrock (Claude) | Enterprise SLAs, AWS ecosystem |
| **Production (GCP)** | Vertex AI (Gemini Pro) | Enterprise SLAs, GCP ecosystem |

---

## Next Steps

1. Choose your provider based on development phase
2. Update `.env` with appropriate settings
3. Test API endpoints: `curl localhost:8000/ask`
4. Benchmark performance: `python scripts/benchmark_llm.py`
5. Document results in portfolio

For implementation details, see:
- [ADR-003: LLM Deployment Strategy](../../docs/adr/003-llm-deployment.md)
- [Phase 5 Implementation Plan](../../docs/IMPLEMENTATION.md#phase-5)
