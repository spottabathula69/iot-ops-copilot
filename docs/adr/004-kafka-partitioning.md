# ADR-004: Kafka Partitioning Strategy

**Status**: Accepted

**Date**: 2026-02-04

**Deciders**: Platform Team

**Technical Story**: Determine optimal Kafka topic partitioning strategy for multi-tenant IoT platform handling millions of devices.

## Context and Problem Statement

We need to partition Kafka topics for:
- **Telemetry**: ~1 message/device/minute (high volume)
- **Events**: State changes, errors (medium volume)
- **Alerts**: Actionable alerts (low volume)

Key considerations:
- **Ordering**: Guarantee message order per device
- **Scalability**: Support 1k-10k customers with 100-10k devices each (up to 1M total devices)
- **Consumer Parallelism**: Enable parallel processing across partitions
- **Multi-tenancy**: Tenant isolation for security and blast radius

## Decision Drivers

- **Partition Cardinality**: Kafka practical limit ~1,000-5,000 partitions per topic
- **Ordering Guarantee**: Messages from same key go to same partition (ordered)
- **Consumer Scaling**: Number of consumers ≤ number of partitions
- **Tenant Isolation**: Prevent one customer's spike from affecting others
- **Rebalancing**: Minimize consumer group rebalancing

## Considered Options

- Option 1: **Partition by device_id** (INCORRECT)
- Option 2: **Partition by customer_id** (CHOSEN)
- Option 3: **Partition by customer_id + facility_id** (Future)

## Decision Outcome

**Chosen option**: "Partition by `customer_id`"

Use consistent hash of `customer_id` as partition key for all Kafka topics.

### Partition Configuration

| Topic | Partitions | Key | Rationale |
|-------|------------|-----|-----------|
| `telemetry` | 100 | `customer_id` | 100-1k customers → ~1-10 customers/partition |
| `events` | 50 | `customer_id` | Lower volume, fewer partitions needed |
| `alerts` | 20 | `customer_id` | Very low volume |

### Partitioning Logic

```python
# Producer
partition = murmurhash(customer_id) % num_partitions

# Example:
customer_id = "acme-manufacturing"
partition = murmurhash("acme-manufacturing") % 100
# → partition 42

# All devices from acme-manufacturing go to partition 42
```

### Consequences

**Good**:
- ✅ **Scalable**: Supports millions of devices (cardinality=customers, not devices)
- ✅ **Tenant Isolation**: All data for one customer in same partition
- ✅ **Ordering**: Per-customer ordering (sufficient for most use cases)
- ✅ **Consumer Scaling**: Can run up to 100 consumers (one per partition)
- ✅ **Rebalancing**: Adding customers doesn't require rebalancing

**Bad**:
- ⚠️ **Hot Partitions**: Large customers may create skewed load
- ⚠️ **No Per-Device Ordering**: Devices from same customer may be out of order (acceptable)
- ⚠️ **Customer Growth**: Very large customers may need sub-partitioning

**Neutral**:
- Query patterns: Most queries are per-customer anyway (natural fit)

### Hot Partition Mitigation

If a customer becomes very large (>10k devices):

**Option 1**: Sub-partition by facility
```python
# For customers with >10k devices
partition_key = f"{customer_id}:{facility_id}"
partition = murmurhash(partition_key) % num_partitions
```

**Option 2**: Dedicated topic for mega-customers
```python
if is_mega_customer(customer_id):
    topic = f"telemetry-{customer_id}"  # dedicated topic
else:
    topic = "telemetry"  # shared topic
```

## Pros and Cons of the Options

### Option 1: Partition by device_id (INCORRECT)

**Description**: Use `device_id` as partition key

**Example**:
```python
partition = hash(device_id) % num_partitions
# device_id="cnc-001" → partition 7
# device_id="cnc-002" → partition 42
```

**Pros**:
- ✅ Perfect ordering per device
- ✅ Even distribution of load (devices have similar throughput)

**Cons**:
- ❌ **Doesn't scale**: 1M devices → need 1M partitions (Kafka limit: ~5k)
- ❌ **Consumer assignment**: Can't have more consumers than partitions
- ❌ **Rebalancing**: Adding devices causes frequent rebalancing
- ❌ **No tenant isolation**: Customer data scattered across all partitions

**Verdict**: **Rejected** - fundamentally doesn't scale

---

### Option 2: Partition by customer_id (CHOSEN)

**Description**: Use `customer_id` as partition key

**Example**:
```python
partition = hash(customer_id) % 100
# customer_id="acme-manufacturing" → partition 42
# All 5000 devices from acme-manufacturing → partition 42
```

**Pros**:
- ✅ **Scalable**: 100-1k customers fit in 100 partitions
- ✅ **Tenant isolation**: All customer data in same partition
- ✅ **Consumer parallelism**: Up to 100 consumers
- ✅ **Query-friendly**: Most queries are per-customer
- ✅ **Stable**: Adding customers doesn't require rebalancing

**Cons**:
- ⚠️ **Hot partitions**: Large customers may skew load
- ⚠️ **No per-device ordering**: Multiple devices from same customer may be out of order

**Verdict**: **Accepted** - best balance of scalability and operational simplicity

---

### Option 3: Partition by customer_id + facility_id

**Description**: Use composite key for very large customers

**Example**:
```python
if customer_device_count > 10000:
    partition_key = f"{customer_id}:{facility_id}"
else:
    partition_key = customer_id
    
partition = hash(partition_key) % num_partitions
```

**Pros**:
- ✅ Mitigates hot partition problem
- ✅ Better load distribution for mega-customers

**Cons**:
- ⚠️ More complex producer logic (conditional)
- ⚠️ Cross-facility queries require reading multiple partitions

**Verdict**: **Future enhancement** - implement when we have customers with >10k devices

---

## Implementation

### Producer Configuration

```python
# apps/simulator/producer.py
from kafka import KafkaProducer
import json

producer = KafkaProducer(
    bootstrap_servers=['kafka:9092'],
    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
    key_serializer=lambda k: k.encode('utf-8'),
    partitioner='murmur2',  # Default, consistent hashing
    acks='all',  # Wait for all replicas
    compression_type='gzip'
)

def send_telemetry(device_id, customer_id, metrics):
    message = {
        "device_id": device_id,
        "customer_id": customer_id,
        "timestamp": datetime.utcnow().isoformat(),
        "metrics": metrics
    }
    
    # Partition key = customer_id
    producer.send(
        topic='telemetry',
        key=customer_id,  # ← This determines partition
        value=message
    )
```

### Consumer Configuration

```python
# apps/ingestion/consumer.py
from kafka import KafkaConsumer

consumer = KafkaConsumer(
    'telemetry',
    bootstrap_servers=['kafka:9092'],
    group_id='telemetry-to-postgres',
    auto_offset_reset='earliest',
    enable_auto_commit=True,
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)

# Each consumer in group gets assigned partitions
# With 100 partitions and 10 consumers → each consumer gets 10 partitions
for message in consumer:
    customer_id = message.key.decode('utf-8')
    telemetry = message.value
    
    # All messages from same customer_id arrive in order
    write_to_postgres(telemetry)
```

### Scaling Consumers

```bash
# Current: 1 consumer
kubectl scale deployment telemetry-consumer --replicas=1

# Scale to 10 consumers (each handles 10 partitions)
kubectl scale deployment telemetry-consumer --replicas=10

# Max: 100 consumers (one per partition)
kubectl scale deployment telemetry-consumer --replicas=100
```

---

## Monitoring

**Metrics to track**:

```promql
# Partition lag (per partition)
kafka_consumer_lag{topic="telemetry", partition="42"}

# Messages per partition (detect hot partitions)
rate(kafka_topic_partition_messages_in_total{partition="42"}[5m])

# Consumer throughput
rate(kafka_consumer_fetch_total[5m])
```

**Alerts**:
```yaml
# Alert if any partition has >1000 messages lag
- alert: KafkaConsumerLag
  expr: kafka_consumer_lag > 1000
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Partition {{ $labels.partition }} lag: {{ $value }}"

# Alert if partition is hot (10x average)
- alert: KafkaHotPartition
  expr: |
    rate(kafka_topic_partition_messages_in_total[5m])
    > 10 * avg(rate(kafka_topic_partition_messages_in_total[5m]))
  for: 10m
  labels:
    severity: warning
```

---

## Future Considerations

### When to Increase Partitions

**Trigger**: Consumer lag consistently >1000 messages AND 100% CPU utilization on consumers

**Action**:
1. Increase partitions: 100 → 200 (one-time operation)
2. Scale consumers: 10 → 20
3. **Warning**: Changing partition count requires re-keying (breaks ordering temporarily)

### When to Sub-Partition

**Trigger**: Single customer generates >20% of total traffic (hot partition)

**Action**: Implement Option 3 (customer_id + facility_id) for that customer

---

## More Information

- Kafka partitioning best practices: https://kafka.apache.org/documentation/#design_partitioning
- Confluent partitioning guide: https://www.confluent.io/blog/how-choose-number-topics-partitions-kafka-cluster/
- Related ADRs:
  - ADR-008: Hyperscale Architecture (when to migrate to multi-region Kafka)
