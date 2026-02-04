# ADR-008: Hyperscale Architecture (1M+ Customers)

**Status**: Proposed (Future Enhancement)

**Date**: 2026-02-04

**Deciders**: Platform Team

**Technical Story**: Document path to scale from current architecture (100-1k customers) to hyperscale (1M+ customers) for portfolio and future growth planning.

## Context and Problem Statement

Current architecture is designed for **100-1,000 customers** with single Kafka cluster, single Postgres instance, and single K8s cluster. This works well for MVP and initial growth, but does not scale to:

- **1,000,000 customers**
- **10,000,000+ devices**
- **1 billion+ telemetry messages per day**
- **Multi-region, global deployment**

This ADR documents the **future architecture** needed to support hyperscale. This is **NOT being implemented in Phase 0-6**, but serves as:
1. Portfolio demonstration of architectural thinking
2. Roadmap for future growth
3. Design validation that current choices don't create dead-ends

## Decision Drivers

- **Blast Radius**: Limit impact of failures (cell-based isolation)
- **Regional Compliance**: Data sovereignty (EU, US, APAC)
- **Cost Efficiency**: Linear cost scaling with customers (~0.3-0.5% of revenue)
- **Operational Simplicity**: Avoid overly complex distributed systems until needed
- **Gradual Migration**: Ability to migrate incrementally without rewrite

## Scaling Tiers

### Tier 1: 100-1,000 Customers (Current - Phase 0-6)

**Architecture**:
```
Single Kafka Cluster (100 partitions)
Single Postgres Instance
Single K8s Cluster (kind/minikube → EKS/GKE)
```

**Partitioning**: `customer_id` hash across 100 Kafka partitions

**Capacity**:
- Kafka: 10k msg/sec
- Postgres: 10k writes/sec
- Devices: Up to 100k

**Cost**: ~$2-5k/month (cloud)

---

### Tier 2: 1,000-10,000 Customers

**Changes**:
1. **Kafka**: Increase to 500 partitions, 6-9 brokers
2. **Database Sharding**: Postgres → Citus (10 shards by customer_id)
3. **Storage Tiering**: 
   - Hot (7d): Postgres
   - Warm (30d): S3 Parquet + Athena
   - Cold (1y): S3 Glacier

**Capacity**:
- Kafka: 50k msg/sec
- Postgres: 50k writes/sec (sharded)
- Devices: Up to 1M

**Cost**: ~$15-30k/month

---

### Tier 3: 10,000-100,000 Customers

**Changes**:
1. **Multi-Region Kafka**: 
   - US-East, EU-West, APAC clusters
   - Customer-region affinity
   - MirrorMaker 2 for cross-region analytics

2. **Database**: 100 shards across regions

3. **Read Replicas**: Separate analytics replicas from transactional DBs

**Capacity**:
- Kafka: 200k msg/sec (across regions)
- Postgres: 200k writes/sec (sharded)
- Devices: Up to 10M

**Cost**: ~$80-120k/month

---

### Tier 4: 100,000-1,000,000 Customers (Hyperscale)

**Cell-Based Architecture** (Stripe, Facebook pattern):

```
┌─────────────────────────────────────────────────┐
│              Control Plane                      │
│  - Customer → Cell routing table                │
│  - API Gateway (Kong/Envoy)                     │
│  - Global monitoring & alerting                 │
└────────┬────────────────────────────────────────┘
         │
    ┌────┴─────┬──────────┬──────────┬─────────┐
    │          │          │          │         │
┌───▼────┐ ┌──▼────┐ ┌───▼────┐ ┌──▼────┐ ┌──▼────┐
│ Cell 1 │ │Cell 2 │ │ Cell 3 │ │Cell 4 │ │Cell...│
│US-East │ │US-West│ │EU-West │ │ APAC  │ │  10   │
│100k    │ │100k   │ │100k    │ │100k   │ │100k   │
│customers│ │customers│ │customers│ │customers│ │customers│
└────────┘ └───────┘ └────────┘ └───────┘ └───────┘
```

**Each Cell Contains**:
- Kafka Cluster (500 partitions)
- Postgres Shards (10 shards)
- K8s Cluster (dedicated)
- S3 bucket (partitioned)
- Copilot API instances
- RAG vector DB shard

**Customer → Cell Mapping**:
```python
# Hybrid: region + hash
cell_id = get_customer_region(customer_id)  # compliance requirement
# Or pure hash for non-regulated
cell_id = hash(customer_id) % NUM_CELLS
```

**Benefits**:
- ✅ **Blast Radius**: Cell 1 outage doesn't affect Cell 2
- ✅ **Regional Compliance**: EU customers in EU cell (GDPR)
- ✅ **Independent Scaling**: Scale cells based on load
- ✅ **Operational Simplicity**: Smaller, manageable clusters
- ✅ **Cost Isolation**: Per-cell cost tracking

**Capacity** (10 cells):
- Kafka: 500k msg/sec (total)
- Postgres: 500k writes/sec (total)
- Devices: Up to 100M
- Customers: Up to 1M

**Cost**: ~$150-200k/month

---

## Key Technology Changes for Hyperscale

### Data Ingestion

**Current**: Apache Kafka  
**Hyperscale Options**:
1. **Apache Pulsar** (better multi-tenancy, geo-replication)
2. **AWS Kinesis** (fully managed, auto-scaling)
3. **Stick with Kafka** (proven, mature, requires more ops)

**Recommendation**: Kafka (current) → Pulsar (if multi-tenancy becomes bottleneck)

---

### Database

**Current**: Postgres + Citus (sharding extension)  
**Hyperscale Options**:
1. **Vitess** (MySQL sharding, proven at YouTube scale)
2. **CockroachDB** (auto-sharding, global distribution)
3. **DynamoDB** (serverless, infinite scale, but NoSQL)

**Recommendation**: Citus (Tier 2-3) → Vitess or CockroachDB (Tier 4)

---

### Analytics Pipelines

**Current**: Airflow (orchestrating Spark jobs)  
**Hyperscale**: 
- **Databricks** (managed Spark, lakehouse optimizations)
- **Apache Spark on K8s** (dynamic scaling to 1000s of pods)
- **Event-driven Lambda** (serverless, for simple aggregations)

**Recommendation**: Airflow + Spark on K8s (cost-effective, flexible)

---

### Vector Database (RAG)

**Current**: pgvector (single instance)  
**Hyperscale**:
1. **Qdrant Cluster** (distributed vector search, horizontal scaling)
2. **Pinecone** (managed, auto-scaling, but expensive)
3. **Sharded pgvector** (10 instances, by customer_id)

**Recommendation**: Qdrant Cluster (open-source, scalable, cost-effective)

---

## Cost Analysis at Hyperscale

### 1 Million Customers, 10M Devices

**Assumptions**:
- 1 billion telemetry messages/day
- 10 million API requests/day
- 1TB new data/day

| Component | Specs | Cost/Month |
|-----------|-------|------------|
| **Kafka** (10 clusters, multi-region) | 90 brokers, 5000 partitions | $30,000 |
| **Database** (100 shards) | 50TB, multi-region | $50,000 |
| **S3 Storage** (1PB, tiered) | Hot 10TB, Warm 100TB, Cold 900TB | $15,000 |
| **Compute** (K8s, 10 cells) | 1000 pods, 4000 vCPUs | $40,000 |
| **LLM API** (OpenAI/Vertex) | 10M queries/day, avg 2k tokens | $20,000 |
| **Monitoring** (Datadog) | 5000 hosts, 50M metrics/min | $10,000 |
| **Network** (egress, cross-region) | 500TB/month | $15,000 |
| **Total** | | **$180,000/month** |

**Revenue Model** (at $50/customer/month):
- Revenue: 1M × $50 = **$50M/month**
- Infrastructure: $180k/month = **0.36% of revenue**
- Healthy unit economics

---

## Migration Path (Gradual)

### Phase 1-6: Single Cluster (Current)
**When**: 0-1,000 customers  
**No migration needed** - building foundation

---

### Phase 7: Database Sharding
**When**: 1,000-5,000 customers  
**Migration**:
1. Set up Citus extension on existing Postgres
2. Distribute existing tables by `customer_id`
3. Add shards incrementally (no downtime)

**Effort**: 2-4 weeks

---

### Phase 8: Multi-Region Kafka
**When**: 5,000-20,000 customers  
**Migration**:
1. Set up regional Kafka clusters
2. Route new customers to regional clusters
3. Migrate existing customers gradually (by region)

**Effort**: 1-2 months

---

### Phase 9: Cell Architecture
**When**: 50,000+ customers  
**Migration**:
1. Define cell boundaries (region + customer hash)
2. Provision Cell 1 (replica of current architecture)
3. Migrate 10% of customers to Cell 1 (canary)
4. Provision Cell 2-10 over 6 months
5. Migrate remaining customers incrementally

**Effort**: 6-12 months (can run dual-stack during migration)

---

## Operational Complexity

### Current (Single Cluster)
- **Ops Team Size**: 2-3 engineers
- **On-Call**: 1 rotation
- **Deployment Frequency**: Daily
- **MTTR**: < 1 hour

### Hyperscale (Cell Architecture)
- **Ops Team Size**: 10-15 engineers (SRE team)
- **On-Call**: 3-4 rotations (regional)
- **Deployment Frequency**: Multiple/day (via canary cells)
- **MTTR**: < 30 minutes (cell isolation limits blast radius)

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Over-engineering too early** | Wasted time, complexity | Don't implement until Tier 2 scale (1k customers) |
| **Data migration failure** | Downtime, data loss | Dual-write strategy, incremental migration |
| **Cell imbalance** | Hot cells, poor UX | Dynamic customer rebalancing, cell splitting |
| **Cross-cell queries slow** | Analytics degraded | Maintain global read replicas for analytics |
| **Increased operational burden** | Burnout, incidents | Invest in automation, SRE practices |

---

## Decision Outcome

**Chosen strategy**: **Cell-based architecture** at hyperscale (Tier 4)

**Implementation Timeline**:
- **Now (Phase 0-6)**: Single cluster, design for sharding
- **6 months**: Database sharding (Tier 2)
- **12 months**: Multi-region Kafka (Tier 3)
- **24 months**: Cell architecture (Tier 4)

**Portfolio Value**: Demonstrates:
- ✅ Understanding of distributed systems at scale
- ✅ Cost awareness and unit economics
- ✅ Pragmatic approach (start simple, scale when needed)
- ✅ Real-world migration planning (not just greenfield design)

---

## Success Metrics

| Metric | Current | Tier 2 | Tier 3 | Tier 4 |
|--------|---------|--------|--------|--------|
| **Customers** | 100-1k | 1k-10k | 10k-100k | 100k-1M |
| **p95 API Latency** | < 2s | < 2s | < 2s | < 2s |
| **Availability** | 99.5% | 99.9% | 99.95% | 99.99% |
| **Infra Cost / Customer** | $3-5 | $2-3 | $1-2 | $0.18 |
| **Ops Team Size** | 2-3 | 3-5 | 5-10 | 10-15 |

---

## More Information

- Stripe's cell-based architecture: https://stripe.com/blog/online-migrations
- Uber's migration to microservices: https://www.uber.com/blog/microservice-architecture/
- Related ADRs:
  - ADR-001: Local Kubernetes (kind)
  - ADR-002: GitOps (Argo CD)
  - ADR-004: Kafka Partitioning Strategy
  - ADR-005: Data Lakehouse Architecture
