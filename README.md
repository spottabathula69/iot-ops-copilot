# IoT Ops Copilot

> **Production-grade IoT Telemetry + AI-powered Troubleshooting Platform**
> 
> A portfolio project demonstrating DevOps, SRE, MLOps, and AI Engineering best practices at scale.

## 🎯 Project Overview

The **IoT Ops Copilot** is an end-to-end platform that ingests IoT device telemetry, processes it through orchestrated data pipelines, builds a hybrid RAG knowledge base, and serves an AI-powered copilot for insights and troubleshooting. Designed to scale to millions of customers with multi-tenant architecture.

### Key Capabilities

- **Real-time Ingestion**: Kafka-based event streaming for IoT telemetry and events
- **Data Orchestration**: Apache Airflow pipelines for ETL (bronze/silver/gold layers)
- **Hybrid RAG**: Combines standard documentation with generated telemetry insights
- **AI Copilot**: LLM-powered Q&A, insights, and troubleshooting with citations
- **Production Observability**: Prometheus/Grafana with custom SLOs and error budgets
- **GitOps**: Infrastructure and app deployment via Terraform + Argo CD
- **Multi-tenant Ready**: Architecture designed for customer isolation at scale

## 🏗️ Architecture

```
┌─────────────┐      ┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   IoT       │─────▶│   Kafka     │─────▶│   Airflow    │─────▶│  RAG Store  │
│ Simulator   │      │  Cluster    │      │  Pipelines   │      │  (Vector)   │
└─────────────┘      └─────────────┘      └──────────────┘      └─────────────┘
                            │                                            │
                            ▼                                            ▼
                     ┌─────────────┐                            ┌─────────────┐
                     │   MinIO/S3  │                            │  Copilot    │
                     │  (Bronze)   │                            │    API      │
                     └─────────────┘                            └─────────────┘
                            │                                            │
                            ▼                                            ▼
                     ┌─────────────┐                            ┌─────────────┐
                     │  Postgres   │                            │     UI      │
                     │ (Silver/Gold)│                            │  (Streamlit)│
                     └─────────────┘                            └─────────────┘

                     ┌────────────────────────────────────────────────────────┐
                     │         Observability Stack (Prometheus/Grafana)       │
                     └────────────────────────────────────────────────────────┘
```

## 🛠️ Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Container Orchestration** | Kubernetes (kind/minikube → EKS/GKE) | Service deployment & management |
| **Streaming** | Apache Kafka (Strimzi operator) | Event ingestion & processing |
| **Data Orchestration** | Apache Airflow | ETL pipeline orchestration (bronze/silver/gold) |
| **Storage** | PostgreSQL + MinIO/S3 | Structured data + object storage |
| **RAG** | Hybrid search (BM25 + Vector), Cross-encoder reranking | Document retrieval & relevance |
| **Embeddings** | sentence-transformers (all-MiniLM-L6-v2) | Text embeddings for semantic search |
| **LLM** | vLLM + TinyLlama/Llama-2 | GPU-accelerated local inference (0.6s latency) |
| **API** | FastAPI + Pydantic | Production-ready async REST API |
| **Observability** | **Prometheus + Grafana + Jaeger + OpenTelemetry** | Metrics, dashboards, distributed tracing, SLOs |
| **GitOps** | Argo CD + Terraform | Declarative infrastructure & deployments |
| **CI/CD** | GitHub Actions | Automated testing & deployment |

**Cost**: $0 - All inference runs locally on GPU, no cloud API calls!

## 📁 Repository Structure

```
iot-ops-copilot/
├── apps/                      # Microservices
│   ├── simulator/            # IoT device simulator (Go/Python)
│   ├── ingestion/            # Kafka consumers
│   ├── rag-service/          # Document ingestion & retrieval
│   ├── copilot-api/          # FastAPI backend
│   └── copilot-ui/           # Streamlit/React frontend
├── charts/                    # Helm charts / Kustomize manifests
├── gitops/                    # Argo CD applications
│   ├── bootstrap/            # App-of-apps
│   └── apps/                 # Individual app specs
├── infra/terraform/           # Infrastructure code
│   ├── bootstrap/            # Initial cluster setup
│   ├── modules/              # Reusable modules
│   └── envs/                 # Environment configs (local/dev/prod)
├── docs/                      # Documentation
│   ├── adr/                  # Architecture Decision Records
│   ├── runbooks/             # Operational playbooks
│   ├── diagrams/             # Architecture diagrams
│   └── slos/                 # SLO definitions
├── observability/             # Monitoring & alerting
│   ├── dashboards/           # Grafana JSON dashboards
│   ├── alerts/               # Prometheus alert rules
│   └── queries/              # PromQL examples
├── loadtest/                  # Performance testing scripts
└── scripts/                   # Utility scripts
```

## 🚀 Quick Start

### Prerequisites

- **Tools**: `terraform`, `kubectl`, `helm`, `kind` or `minikube`, `docker`
- **Accounts** (for cloud deployment): AWS/GCP account, OpenAI API key (optional)

### Local Development Setup

```bash
# 1. Clone repository
git clone <repo-url>
cd iot-ops-copilot

# 2. Create local Kubernetes cluster
cd infra/terraform/bootstrap
terraform init
terraform apply

# 3. Deploy Argo CD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# 4. Deploy app-of-apps
kubectl apply -f gitops/bootstrap/app-of-apps.yaml

# 5. Access services
./scripts/port-forward.sh
```

Open browser to:
- Argo CD: http://localhost:8080
- Grafana: http://localhost:3000
- Copilot UI: http://localhost:8501

## 📚 Documentation

- [Architecture Overview](docs/ARCHITECTURE.md)
- [Phase 0-8 Implementation Guide](docs/IMPLEMENTATION.md)
- [Architecture Decision Records (ADRs)](docs/adr/)
- [Runbooks](docs/runbooks/)
- [SLO Definitions](docs/slos/)
- [Benchmarks](docs/BENCHMARKS.md)

## 🎯 Implementation Phases

| Phase | Focus | Status | Highlights |
|-------|-------|--------|------------|
| **Phase 0** | Skeleton + CI + GitOps Bootstrap | ✅ Complete | Repo structure, ADRs, runbooks, kind cluster |
| **Phase 1** | Kafka Ingestion MVP | ✅ Complete | Strimzi Kafka, IoT simulator (4 device types), Postgres+MinIO consumers, Kafka UI |
| **Phase 2** | Airflow Orchestration | ✅ Complete | Airflow 2.8.3 on K8s, Bronze→Silver→Gold DAGs, data transformations |
| **Phase 3** | RAG Ingestion | 100% | ✅ Complete | [apps/rag/](apps/rag/) |
| **Phase 4** | RAG Quality | 90% | ✅ Complete | [Hybrid Search](apps/rag/HYBRID_README.md) |
| **Phase 5** | Copilot Service | 60% | 🚧 In Progress | [apps/copilot-api/](apps/copilot-api/) |
| **Phase 6** | Observability | 0% | 📝 Planned | Prometheus, Grafana, custom metrics, error budgets |
| **Phase 7** | Scale Story (Multi-tenant) | ⏳ Pending | Tenant isolation, quotas, load testing |
| **Phase 8** | Security & Enterprise Polish | ⏳ Pending | AuthN/AuthZ, secrets, audit logs |

## 🔍 Key Features

### Multi-tenant Architecture
- Tenant-aware data model (`tenant_id` isolation)
- Namespace-based resource quotas
- Per-tenant rate limiting and API quotas

### Hybrid RAG Pipeline
- **BM25 + Vector Similarity** for retrieval
- **Reranking** for precision
- **Citations** with source attribution
- **Freshness Rules** (newer firmware overrides older docs)

### Observability & SLOs
- **RED Method**: Rate, Errors, Duration for all services
- **Custom Metrics**: `answers_with_citations_ratio`, `retrieval_empty_rate`, `hallucination_flag_rate`
- **Error Budgets**: Automated SLO tracking with alert thresholds

### Production-Ready Patterns
- Golden signal metrics (latency, traffic, errors, saturation)
- Circuit breakers and backpressure handling
- Data retention policies (hot/warm/cold tiers)
- Disaster recovery and replay capabilities

## 🧪 Testing & Validation

```bash
# Run unit tests
make test

# Run integration tests
make test-integration

# Load testing
cd loadtest
k6 run --vus 100 --duration 30s copilot-api.js

# RAG quality evaluation
kubectl exec -it <airflow-pod> -- airflow dags test rag_eval_pipeline
```

## 📊 Benchmarks

| Metric | Target | Current |
|--------|--------|---------|
| Copilot API p95 Latency | < 2s | TBD |
| RAG Retrieval p95 | < 500ms | TBD |
| Kafka Consumer Lag | < 1000 msgs | TBD |
| Airflow DAG Success Rate | > 99% | TBD |

## 🤝 Contributing

See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for development workflow, coding standards, and PR guidelines.

## 📝 License

MIT License - See [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

This is a portfolio project designed to demonstrate:
- **DevOps**: Terraform, GitOps (Argo CD), CI/CD
- **SRE**: Observability, SLOs, incident response, capacity planning
- **MLOps**: ML pipeline orchestration, model versioning, evaluation harnesses
- **AI Engineering**: RAG architecture, LLM integration, prompt engineering, tool calling

---

**Status**: ✅ **Phase 3 - RAG Ingestion (90% Complete)**

**Latest Updates** (2026-02-04):
- ✅ Deployed pgvector extension (v0.8.1) on Postgres
- ✅ Built configurable embedding service (local sentence-transformers default, OpenAI optional)
- ✅ Created document chunking pipeline (LangChain, 512-char chunks)
- ✅ Implemented vector similarity search with tenant filtering
- ✅ Sample CNC manual ready for ingestion (Haas VF-2)
- 🚧 Next: Test ingestion, create Airflow DAG, move to Phase 4 (RAG quality)

**Quick Stats**:
- 🔧 **4 Device Types**: CNC machines, Robotic arms, Conveyor belts, 3D printers
- 📊 **2,600+ Telemetry Records**: Bronze (MinIO) → Silver (Postgres) → Gold (aggregations)
- 📚 **Vector DB**: pgvector with 384-dim embeddings, HNSW index
- 🤖 **Zero External Dependencies**: Local embeddings (no API keys needed!)

For questions or feedback, please open an issue or reach out via email.
