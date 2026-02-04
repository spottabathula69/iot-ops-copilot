# Kafka Infrastructure (Strimzi Operator)

This directory contains Kubernetes manifests for deploying Kafka using the **Strimzi operator**.

## Architecture

```
Strimzi Operator (kafka namespace)
├── Kafka Cluster (3 brokers)
│   ├── ZooKeeper ensemble (3 nodes)
│   ├── Entity Operator (Topic & User management)
│   └── Metrics (Prometheus JMX Exporter)
└── Kafka Topics (CRDs)
    ├── telemetry (100 partitions)
    ├── events (50 partitions)
    ├── alerts (20 partitions)
    └── heartbeat (20 partitions)
```

## Files

- `namespace.yaml` - Kafka namespace
- `strimzi-operator.yaml` - Helm values for Strimzi operator
- `kafka-cluster.yaml` - Kafka cluster definition (3 brokers, ZooKeeper)
- `kafka-topics.yaml` - Topic definitions (telemetry, events, alerts, heartbeat)
- `kafka-users.yaml` - Kafka users for applications (optional, TLS auth)

## Quick Start

### 1. Install Strimzi Operator

```bash
# Add Helm repo
helm repo add strimzi https://strimzi.io/charts/
helm repo update

# Install operator
helm install strimzi-kafka-operator strimzi/strimzi-kafka-operator \
  --namespace kafka \
  --create-namespace \
  --values strimzi-operator.yaml
```

### 2. Deploy Kafka Cluster

```bash
# Apply namespace
kubectl apply -f namespace.yaml

# Deploy Kafka cluster (takes 3-5 minutes)
kubectl apply -f kafka-cluster.yaml

# Wait for cluster ready
kubectl wait kafka/iot-ops-kafka --for=condition=Ready --timeout=300s -n kafka
```

### 3. Create Topics

```bash
kubectl apply -f kafka-topics.yaml

# Verify topics
kubectl get kafkatopics -n kafka
```

## Validation

### Check Cluster Health

```bash
# Check pods
kubectl get pods -n kafka

# Expected:
# iot-ops-kafka-zookeeper-0       1/1     Running
# iot-ops-kafka-zookeeper-1       1/1     Running
# iot-ops-kafka-zookeeper-2       1/1     Running
# iot-ops-kafka-kafka-0           1/1     Running
# iot-ops-kafka-kafka-1           1/1     Running
# iot-ops-kafka-kafka-2           1/1     Running
# iot-ops-kafka-entity-operator   3/3     Running
```

### Describe Kafka Cluster

```bash
kubectl describe kafka iot-ops-kafka -n kafka

# Look for: Status: Ready = True
```

### List Topics

```bash
kubectl exec -n kafka iot-ops-kafka-kafka-0 -- \
  bin/kafka-topics.sh --bootstrap-server localhost:9092 --list

# Expected output:
# telemetry
# events
# alerts
# heartbeat
```

### Describe Topic

```bash
kubectl exec -n kafka iot-ops-kafka-kafka-0 -- \
  bin/kafka-topics.sh --bootstrap-server localhost:9092 \
  --describe --topic telemetry

# Check: Partitions: 100, Replication Factor: 3
```

## Test Producer/Consumer

### Produce Messages

```bash
kubectl exec -it -n kafka iot-ops-kafka-kafka-0 -- \
  bin/kafka-console-producer.sh \
  --bootstrap-server localhost:9092 \
  --topic telemetry

# Type messages (Ctrl+C to exit):
# {"device_id": "test-001", "temperature": 25.5}
```

### Consume Messages

```bash
kubectl exec -it -n kafka iot-ops-kafka-kafka-0 -- \
  bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic telemetry \
  --from-beginning \
  --max-messages 10
```

## Connection String (for Apps)

```
Bootstrap Servers: iot-ops-kafka-kafka-bootstrap.kafka.svc.cluster.local:9092
```

**Python Example**:
```python
from kafka import KafkaProducer

producer = KafkaProducer(
    bootstrap_servers='iot-ops-kafka-kafka-bootstrap.kafka.svc.cluster.local:9092'
)
```

## Monitoring

### Prometheus Metrics

Metrics exposed on port `9404`:
```bash
# Port-forward to access metrics
kubectl port-forward -n kafka iot-ops-kafka-kafka-0 9404:9404

# Metrics endpoint
curl http://localhost:9404/metrics | grep kafka_server
```

### Grafana Dashboard

Import Strimzi Kafka dashboard:
- Dashboard ID: `11004`
- Or use custom dashboard: `observability/dashboards/kafka-ingestion.json`

## Troubleshooting

### Broker Not Ready

```bash
# Check broker logs
kubectl logs -n kafka iot-ops-kafka-kafka-0

# Common issues:
# - Insufficient resources (CPU/memory)
# - ZooKeeper connection issues
```

### Topic Creation Failed

```bash
# Check topic operator logs
kubectl logs -n kafka -l strimzi.io/name=iot-ops-kafka-entity-operator -c topic-operator

# Verify KafkaTopic CRD
kubectl get kafkatopic telemetry -n kafka -o yaml
```

### Consumer Lag Growing

```bash
# Check consumer groups
kubectl exec -n kafka iot-ops-kafka-kafka-0 -- \
  bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --list

# Describe consumer group
kubectl exec -n kafka iot-ops-kafka-kafka-0 -- \
  bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --group telemetry-to-postgres \
  --describe
```

## Cleanup

```bash
# Delete Kafka cluster
kubectl delete -f kafka-cluster.yaml

# Delete topics
kubectl delete -f kafka-topics.yaml

# Uninstall operator
helm uninstall strimzi-kafka-operator -n kafka

# Delete namespace
kubectl delete namespace kafka
```

## More Information

- [ADR-007: Kafka Operator Choice](../../docs/adr/007-kafka-operator.md)
- [Strimzi Documentation](https://strimzi.io/docs/operators/latest/)
- [Kafka Topic Configuration](https://kafka.apache.org/documentation/#topicconfigs)
