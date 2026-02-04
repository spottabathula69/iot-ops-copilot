# Copilot API

**Status**: Phase 5 - Not Yet Implemented

This directory will contain the FastAPI backend for the IoT Ops Copilot.

## Planned Features (Phase 5)

- **Endpoints**:
  - `POST /ask` - Q&A grounded in RAG + telemetry
  - `GET /insights/{device_id}` - Device health summary
  - `POST /troubleshoot` - Step-by-step diagnostic guide
- **Capabilities**:
  - LLM integration (OpenAI/Anthropic/Local)
  - RAG retrieval with citations
  - Tool/function calling for telemetry queries
  - Response caching (Redis)
  - Guardrails (prompt injection, PII detection)
  - Per-tenant rate limiting

## Directory Structure (Future)

```
copilot-api/
├── app/
│   ├── main.py              # FastAPI app
│   ├── routes/              # API endpoints
│   ├── services/            # Business logic
│   │   ├── rag.py
│   │   ├── llm.py
│   │   └── telemetry.py
│   └── models/              # Pydantic models
├── tests/
├── requirements.txt
├── Dockerfile
└── README.md
```

---

See [Phase 5 Implementation Plan](../../docs/IMPLEMENTATION.md#phase-5) for details.
