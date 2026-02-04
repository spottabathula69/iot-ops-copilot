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
| **Event Streaming** | Apache Kafka (Strimzi operator) | Real-time telemetry ingestion |
| **Workflow Orchestration** | Apache Airflow (on K8s) | Data pipeline scheduling |
| **Vector Database** | pgvector / Qdrant / Milvus | RAG knowledge store |
| **Object Storage** | MinIO (local) / S3 | Bronze layer (raw data) |
| **Database** | PostgreSQL | Silver/gold layers (curated data) |
| **LLM** | OpenAI / Anthropic / Local | Copilot intelligence |
| **Infrastructure as Code** | Terraform | Cluster & resource provisioning |
| **GitOps** | Argo CD | Declarative deployment |
| **Observability** | Prometheus + Grafana | Metrics, dashboards, alerts |
| **Load Testing** | k6 / hey | Performance benchmarking |

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

| Phase | Focus | Status |
|-------|-------|--------|
| **Phase 0** | Skeleton + CI + GitOps Bootstrap | 🚧 In Progress |
| **Phase 1** | Kafka Ingestion MVP | ⏳ Pending |
| **Phase 2** | Airflow Orchestration | ⏳ Pending |
| **Phase 3** | RAG Ingestion | ⏳ Pending |
| **Phase 4** | RAG Quality (Hybrid + Citations) | ⏳ Pending |
| **Phase 5** | Copilot Service | ⏳ Pending |
| **Phase 6** | Observability + SLOs | ⏳ Pending |
| **Phase 7** | Scale Story (Multi-tenant) | ⏳ Pending |
| **Phase 8** | Security & Enterprise Polish | ⏳ Pending |

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

**Status**: 🚧 Phase 0 - Bootstrap in progress

For questions or feedback, please open an issue or reach out via email.
