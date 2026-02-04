# ADR-007: Kafka Operator Choice (Strimzi vs Confluent)

**Status**: Accepted

**Date**: 2026-02-04

**Deciders**: Platform Team

**Technical Story**: Select Kafka operator for deploying and managing Kafka clusters on Kubernetes for IoT telemetry ingestion.

## Context and Problem Statement

Need to deploy Kafka on Kubernetes (kind locally, EKS/GKE in production) to ingest IoT device telemetry at scale. Options include:
- Running Kafka manually (StatefulSets, Services)
- Using Kafka operators (Strimzi, Confluent Operator)

Operators provide:
- Declarative Kafka cluster management (CRDs)
- Automated upgrades and scaling
- Topic and user management
- Monitoring and metrics integration

## Decision Drivers

- **Cost**: Open-source vs commercial licensing
- **Maturity**: Production-ready, battle-tested
- **Kubernetes-Native**: CRD-based, follows K8s patterns
- **Monitoring**: Prometheus/Grafana integration
- **Portfolio Value**: Demonstrates cloud-native expertise
- **Vendor Lock-in**: Avoid proprietary dependencies

## Considered Options

- Option 1: **Strimzi Kafka Operator** (CHOSEN)
- Option 2: **Confluent Operator for Kubernetes**
- Option 3: **Manual Kafka Deployment** (StatefulSets)

## Decision Outcome

**Chosen option**: "Strimzi Kafka Operator"

Deploy Kafka using the open-source Strimzi operator for Kubernetes-native cluster management.

### Implementation

**Install Strimzi Operator** (via Helm):
```bash
helm repo add strimzi https://strimzi.io/charts/
helm install strimzi-kafka-operator strimzi/strimzi-kafka-operator \
  --namespace kafka \
  --create-namespace \
  --set watchNamespaces={kafka}
```

**Kafka Cluster Definition** (CRD):
```yaml
apiVersion: kafka.strimzi.io/v1beta2
kind: Kafka
metadata:
  name: iot-ops-kafka
  namespace: kafka
spec:
  kafka:
    version: 3.6.0
    replicas: 3
    listeners:
      - name: plain
        port: 9092
        type: internal
        tls: false
    config:
      num.partitions: 100
      default.replication.factor: 3
      min.insync.replicas: 2
      auto.create.topics.enable: false
    storage:
      type: ephemeral  # For local dev
    metrics:
      # Prometheus JMX Exporter
      lowercaseOutputName: true
      rules:
        - pattern: "kafka.server<type=(.+), name=(.+)><>Value"
          name: kafka_server_$1_$2
  zookeeper:
    replicas: 3
    storage:
      type: ephemeral
  entityOperator:
    topicOperator: {}
    userOperator: {}
```

**Topic Creation**:
```yaml
apiVersion: kafka.strimzi.io/v1beta2
kind: KafkaTopic
metadata:
  name: telemetry
  namespace: kafka
  labels:
    strimzi.io/cluster: iot-ops-kafka
spec:
  partitions: 100
  replicas: 3
  config:
    retention.ms: 604800000  # 7 days
    compression.type: gzip
```

### Consequences

**Good**:
- ✅ **Open-source**: Apache 2.0 license, no vendor fees
- ✅ **CNCF Project**: Graduated project, production-ready
- ✅ **Kubernetes-Native**: CRDs for Kafka, Topics, Users
- ✅ **Prometheus Integration**: Built-in JMX exporter for metrics
- ✅ **Widely Adopted**: Used by Netflix, Red Hat, many enterprises
- ✅ **Portfolio Value**: Shows K8s expertise, avoids vendor lock-in

**Bad**:
- ⚠️ **No Commercial Support**: Community support only (unless Red Hat AMQ)
- ⚠️ **Basic UI**: No built-in Kafka GUI (need external tools like Kafdrop)
- ⚠️ **Manual Scaling**: Need to edit CRD to scale (vs auto-scaling)

**Neutral**:
- Requires understanding of Kafka CRDs (learning curve)
- Community-driven feature development

## Pros and Cons of the Options

### Option 1: Strimzi Kafka Operator (CHOSEN)

**Description**: CNCF Sandbox project for running Kafka on Kubernetes

**Pros**:
- ✅ **Free and Open-Source**: No licensing costs, Apache 2.0
- ✅ **Production-Ready**: Used at scale (Netflix, others)
- ✅ **Declarative**: Full GitOps support via CRDs
- ✅ **Metrics**: Prometheus JMX exporter built-in
- ✅ **Active Development**: Regular releases, responsive maintainers
- ✅ **Documentation**: Comprehensive docs and examples

**Cons**:
- ⚠️ **No GUI**: Need separate tools for UI (Kafdrop, AKHQ)
- ⚠️ **Community Support**: No SLA, relies on GitHub issues

**Cost**: $0

---

### Option 2: Confluent Operator for Kubernetes

**Description**: Confluent's commercial operator for Confluent Platform

**Pros**:
- ✅ **Enterprise Features**: Schema Registry, ksqlDB, Control Center UI
- ✅ **Commercial Support**: SLA, dedicated support team
- ✅ **Advanced Features**: Auto-scaling, tiered storage
- ✅ **Polished UI**: Confluent Control Center for monitoring

**Cons**:
- ❌ **Licensing Costs**: $1,500+/month for production features
- ❌ **Vendor Lock-in**: Proprietary features, harder to migrate
- ❌ **Overkill**: Don't need Schema Registry/ksqlDB for Phase 1
- ❌ **Portfolio**: Less impressive ("used commercial product" vs "managed open-source")

**Cost**: ~$18,000+/year (not suitable for portfolio project)

---

### Option 3: Manual Kafka Deployment (StatefulSets)

**Description**: Deploy Kafka using vanilla Kubernetes resources

**Pros**:
- ✅ **Full Control**: No abstraction layer
- ✅ **Learning**: Deep understanding of Kafka internals

**Cons**:
- ❌ **Operational Burden**: Manual upgrades, scaling, topic management
- ❌ **Error-Prone**: Easy to misconfigure replication, persistence
- ❌ **No Declarative Topics**: Need manual `kafka-topics.sh` commands
- ❌ **Time-Consuming**: 10x more work vs operator

**Verdict**: Rejected - not worth the operational overhead

---

## Strimzi Features We'll Use

### 1. Declarative Cluster Management

```yaml
# Want to scale Kafka? Edit replicas and apply
spec:
  kafka:
    replicas: 5  # Was 3, now 5
```

Strimzi handles:
- Creating new StatefulSet pods
- Updating ZooKeeper ensemble
- Rebalancing partitions

### 2. Declarative Topic Management

```yaml
# Create topic via CRD (GitOps-friendly)
apiVersion: kafka.strimzi.io/v1beta2
kind: KafkaTopic
metadata:
  name: telemetry
spec:
  partitions: 100
  replicas: 3
```

vs manual:
```bash
# Manual approach (not declarative)
kafka-topics.sh --create --topic telemetry --partitions 100 --replication-factor 3
```

### 3. Prometheus Metrics (Built-in)

Strimzi automatically exports:
- `kafka_server_BrokerTopicMetrics_MessagesInPerSec` (throughput)
- `kafka_server_BrokerTopicMetrics_BytesInPerSec` (bytes)
- `kafka_server_ReplicaManager_*` (replication lag)

### 4. Auto-Configuration

Strimzi auto-creates:
- Kubernetes Services (bootstrap, brokers)
- ConfigMaps (broker configs)
- Secrets (inter-broker TLS)

---

## Alternatives Considered (Non-Operators)

### Amazon MSK (Managed Kafka on AWS)
- **Pros**: Fully managed, no K8s needed
- **Cons**: Vendor lock-in, expensive ($100+/month), not for local dev
- **Verdict**: Consider for production (Phase 8), not for portfolio MVP

### Confluent Cloud
- **Pros**: Fully SaaS, easiest
- **Cons**: Most expensive ($1/GB ingress), defeats portfolio purpose
- **Verdict**: Rejected

---

## Monitoring and Observability

Strimzi exposes Prometheus metrics via:
```yaml
spec:
  kafka:
    metrics:
      lowercaseOutputName: true
      rules:
        - pattern: "kafka.server<type=(.+), name=(.+)><>Value"
          name: kafka_server_$1_$2
```

**Key Metrics** (automatically scraped by Prometheus):
- `kafka_server_BrokerTopicMetrics_MessagesInPerSec` - Throughput
- `kafka_server_ReplicaManager_UnderReplicatedPartitions` - Health
- `kafka_consumer_lag` - Consumer progress (need Kafka Exporter)

**Grafana Dashboards**:
- Strimzi Kafka (official dashboard ID: 11004)
- Custom dashboard for IoT-specific metrics

---

## Operational Considerations

### Upgrading Kafka
```yaml
# Change version in CRD
spec:
  kafka:
    version: 3.7.0  # Was 3.6.0
```

Strimzi performs **rolling upgrade** automatically.

### Scaling Brokers
```yaml
spec:
  kafka:
    replicas: 5  # Add 2 brokers
```

Strimzi adds brokers, but **does NOT** rebalance partitions automatically.  
Manual rebalance needed:
```bash
kafka-reassign-partitions.sh --execute --reassignment-json-file plan.json
```

### Disaster Recovery
- Ephemeral storage (local dev): Data lost on pod restart
- Persistent storage (prod): Use PersistentVolumeClaims

---

## Migration Path (Future)

**Local (Phase 1-6)**: Strimzi on kind  
**Staging**: Strimzi on EKS/GKE  
**Production (Option A)**: Strimzi on EKS with EBS volumes  
**Production (Option B)**: Migrate to Amazon MSK (managed)

**Reasoning**: Start with Strimzi (learn Kafka deeply), optionally migrate to MSK for operational simplicity.

---

## Success Metrics

- [ ] Kafka cluster deploys in <5 minutes
- [ ] Topics created declaratively via CRDs
- [ ] Prometheus scrapes Kafka metrics (30+ metrics)
- [ ] Grafana dashboard shows broker health
- [ ] Zero manual `kafka-topics.sh` commands needed
- [ ] GitOps: All Kafka config in Git, synced via Argo CD

---

## More Information

- Strimzi Docs: https://strimzi.io/docs/operators/latest/
- Strimzi GitHub: https://github.com/strimzi/strimzi-kafka-operator
- Confluent Operator: https://docs.confluent.io/operator/current/overview.html
- Related ADRs:
  - ADR-001: Local Kubernetes (kind)
  - ADR-002: GitOps Tooling (Argo CD)
  - ADR-004: Kafka Partitioning Strategy
