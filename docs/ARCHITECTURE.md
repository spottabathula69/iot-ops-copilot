# Architecture Overview

## System Context

The **IoT Ops Copilot** platform processes telemetry from millions of IoT devices, transforms it into actionable insights, and serves an AI-powered copilot for troubleshooting and operational intelligence.

## Design Principles

1. **Event-Driven**: Kafka as the central nervous system for all device events
2. **Data Lakehouse**: Bronze (raw) → Silver (curated) → Gold (aggregated) layers
3. **AI-First**: RAG-grounded LLM with tool calling for contextual answers
4. **Multi-tenant**: Customer isolation at data, infrastructure, and API layers
5. **Observable**: Prometheus metrics, distributed tracing, structured logs
6. **GitOps**: Declarative infrastructure and application deployment
7. **Scalable**: Horizontal scaling for all stateless services; partitioning for stateful

## Component Architecture

### Data Ingestion Layer

```
IoT Devices (millions)
    │
    ├─▶ MQTT/HTTP Gateway ─▶ Kafka Producer
    │                         │
    │                         ├─▶ telemetry topic (partitioned by device_id)
    │                         ├─▶ events topic (device state changes)
    │                         └─▶ alerts topic (anomalies, thresholds)
    │
    └─▶ Kafka Consumers
        ├─▶ Bronze Writer (MinIO/S3) - raw JSON blobs
        ├─▶ Silver Writer (Postgres) - normalized tables
        └─▶ Real-time Alerting
```

**Key Decisions**:
- Kafka partitioning by `device_id` for ordering guarantees
- Consumer groups for parallel processing
- Idempotent consumers (exactly-once semantics via offset tracking)

### Data Processing Layer (Airflow)

```
Airflow Scheduler
    │
    ├─▶ DAG: bronze_to_silver (hourly)
    │   └─▶ Parquet conversion + schema enforcement
    │
    ├─▶ DAG: silver_to_gold (daily)
    │   └─▶ Aggregations: device health scores, customer summaries
    │
    ├─▶ DAG: enrichment (on-demand)
    │   └─▶ Join error_codes with KB articles
    │
    ├─▶ DAG: doc_ingestion (on file change)
    │   └─▶ Chunking → Embeddings → Vector DB
    │
    └─▶ DAG: rag_evaluation (weekly)
        └─▶ Test harness: precision/recall, citation accuracy
```

**Key Decisions**:
- KubernetesExecutor for dynamic pod scaling
- Data-aware scheduling (files in MinIO trigger DAGs)
- Retry policies with exponential backoff
- Lineage tracking via Airflow metadata

### Knowledge Layer (RAG)

```
┌─────────────────────────────────────────────┐
│          Document Ingestion                 │
│  Manuals, Runbooks, KB, Firmwares          │
└──────────────┬──────────────────────────────┘
               │ Chunking (semantic)
               ▼
┌─────────────────────────────────────────────┐
│          Embedding Generation               │
│    Model: sentence-transformers (768-dim)   │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│          Vector Store (pgvector)            │
│  + Metadata: tenant_id, version, freshness  │
│  + BM25 Index (Elasticsearch)              │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│        Hybrid Retrieval Pipeline            │
│  1. Vector Similarity (top 50)             │
│  2. BM25 Keyword Match (top 50)            │
│  3. Merge + Rerank (cross-encoder, top 10) │
│  4. Citation Extraction                     │
└──────────────┬──────────────────────────────┘
               │
               ▼
           LLM Context
```

**Key Decisions**:
- **Vector DB**: `pgvector` (collocated with Postgres for simplicity; scales to 10M+ vectors)
- **Embedding Model**: `all-MiniLM-L6-v2` (fast inference, 384-dim, good quality)
- **Hybrid Retrieval**: BM25 for exact matches + vectors for semantic similarity
- **Reranking**: `cross-encoder/ms-marco-MiniLM-L-6-v2` for precision boost
- **Freshness**: Boost recent documents by 1.2x score multiplier

See [ADR-003: Vector Database Selection](adr/003-vector-db-selection.md)

### Copilot Service Layer

```
┌─────────────────────────────────────────────┐
│           FastAPI Service                   │
│                                             │
│  POST /ask                                  │
│    ├─▶ Input validation + guardrails       │
│    ├─▶ RAG retrieval (hybrid)              │
│    ├─▶ Tool/function calling:              │
│    │     - get_device_metrics(device_id)   │
│    │     - get_incident_history(tenant_id) │
│    │     - fetch_related_docs(error_code)  │
│    ├─▶ LLM prompt construction             │
│    ├─▶ LLM call (OpenAI/Anthropic)         │
│    ├─▶ Citation injection                  │
│    └─▶ Response caching (Redis)            │
│                                             │
│  GET /insights/{device_id}                 │
│    ├─▶ Query gold layer (Postgres)         │
│    ├─▶ Health score + recent events        │
│    └─▶ Suggested actions (rule-based)      │
│                                             │
│  POST /troubleshoot                         │
│    ├─▶ Multi-step workflow                 │
│    ├─▶ Diagnostic checks (tool calling)    │
│    └─▶ Step-by-step guide with citations   │
└─────────────────────────────────────────────┘
```

**Key Decisions**:
- **Framework**: FastAPI (async, auto OpenAPI docs, Pydantic validation)
- **LLM**: OpenAI GPT-4 (production) + local Llama 3.1 (fallback/cost control)
- **Caching**: Redis for identical queries (30-min TTL)
- **Rate Limiting**: `slowapi` with per-tenant quotas
- **Guardrails**: Prompt injection detection (Lakera Guard), PII scrubbing

See [ADR-005: LLM Selection and Guardrails](adr/005-llm-selection.md)

### Observability Stack

```
┌─────────────────────────────────────────────┐
│              Prometheus                     │
│  ┌───────────────────────────────────────┐ │
│  │ Service Metrics (RED)                 │ │
│  │  - http_request_duration_seconds      │ │
│  │  - http_requests_total                │ │
│  │  - http_request_errors_total          │ │
│  ├───────────────────────────────────────┤ │
│  │ Kafka Metrics                         │ │
│  │  - kafka_consumer_lag                 │ │
│  │  - kafka_messages_consumed_total      │ │
│  ├───────────────────────────────────────┤ │
│  │ Airflow Metrics                       │ │
│  │  - airflow_dag_duration_seconds       │ │
│  │  - airflow_task_failures_total        │ │
│  ├───────────────────────────────────────┤ │
│  │ RAG Metrics (Custom)                  │ │
│  │  - rag_retrieval_latency_seconds      │ │
│  │  - rag_empty_results_ratio            │ │
│  │  - rag_citation_ratio                 │ │
│  ├───────────────────────────────────────┤ │
│  │ LLM Metrics                           │ │
│  │  - llm_ttft_seconds (time to first)   │ │
│  │  - llm_tokens_per_second              │ │
│  │  - llm_cost_per_request               │ │
│  └───────────────────────────────────────┘ │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│              Grafana                        │
│  - RED dashboards (per service)            │
│  - Kafka lag alerts                        │
│  - SLO burn rate visualizations            │
│  - Golden signals overview                 │
└─────────────────────────────────────────────┘
```

**SLO Definitions**:

| Service | SLI | Target | Error Budget |
|---------|-----|--------|--------------|
| Copilot API | p95 latency < 2s | 99.5% | 0.5% (216 min/month) |
| RAG Retrieval | p95 latency < 500ms | 99.9% | 0.1% (43 min/month) |
| Kafka Ingestion | Lag < 1000 msgs | 99% | 1% (7.2 hrs/month) |
| Airflow Pipelines | Success rate > 99% | 99% | 1% |

See [docs/slos/](slos/) for full definitions and alert rules.

## Multi-tenancy Architecture

### Tenant Isolation Layers

```
┌─────────────────────────────────────────────┐
│          API Layer                          │
│  - JWT with tenant_id claim                │
│  - Row-level security enforcement          │
│  - Per-tenant rate limits                  │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│          Data Layer                         │
│  Kafka:                                     │
│    - Topics: telemetry_<tenant_id>         │
│  Postgres:                                  │
│    - All tables have tenant_id column      │
│    - RLS policies enabled                  │
│  Vector Store:                              │
│    - Metadata filter: tenant_id            │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│     Infrastructure Layer (Phase 7)          │
│  - Namespace-per-tenant (enterprise tier)  │
│  - Resource quotas (CPU/memory)            │
│  - Network policies                        │
└─────────────────────────────────────────────┘
```

**Partitioning Strategy** (Phase 7):

- **Tier 1 (SMB)**: Shared infrastructure, logical isolation via `tenant_id`
- **Tier 2 (Enterprise)**: Dedicated namespace, shared cluster
- **Tier 3 (Strategic)**: Dedicated cluster

See [ADR-008: Multi-tenancy Model](adr/008-multi-tenancy.md)

## Data Flow (End-to-End)

```
1. Device sends telemetry → Kafka (telemetry topic)
2. Consumer writes to MinIO (bronze/raw/YYYY-MM-DD/HH/device_<id>.json)
3. Airflow DAG (hourly) → reads bronze → writes Parquet to silver
4. Airflow DAG (daily) → aggregates silver → writes to gold (Postgres)
5. User asks question → Copilot API
6. RAG retrieval → combines gold data + KB docs
7. LLM generates answer with citations
8. Frontend displays answer + sources
```

## Security Considerations

- **Network**: Network policies (deny-all default, allow-list)
- **Secrets**: Sealed Secrets (GitOps-friendly) or HashiCorp Vault
- **RBAC**: Least privilege for service accounts
- **Audit Logs**: All API calls logged with `tenant_id`, `user_id`, timestamp
- **Data Encryption**: TLS in transit, volume encryption at rest
- **Image Scanning**: Trivy in CI/CD pipeline

See [docs/THREAT_MODEL.md](THREAT_MODEL.md) for full analysis.

## Disaster Recovery

- **Kafka**: Replication factor 3, min in-sync replicas 2
- **Postgres**: WAL archiving to S3, PITR capability
- **Vector DB**: Snapshot backups (daily), stored in S3
- **Bootstrap**: Terraform state in S3 with versioning
- **Recovery Time Objective (RTO)**: < 1 hour
- **Recovery Point Objective (RPO)**: < 15 minutes

## Future Extensions (Post-Phase 8)

- **Streaming ML**: Apache Flink for real-time anomaly detection
- **Service Mesh**: Istio for mTLS, traffic splitting, circuit breakers
- **Progressive Delivery**: Flagger for canary deployments
- **FinOps**: Kubecost for cost attribution per tenant
- **Data Governance**: Apache Atlas for lineage, Amundsen for discovery

---

**Last Updated**: 2026-02-04
**Version**: 0.1.0 (Phase 0)
