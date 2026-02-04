# ADR-006: Device Offline/Online Handling

**Status**: Accepted

**Date**: 2026-02-04

**Deciders**: Platform Team

**Technical Story**: Handle cases where IoT devices go offline (network issues, power loss, maintenance) and later come back online, potentially with buffered/late-arriving data.

## Context and Problem Statement

Industrial equipment devices may experience:
- **Network outages**: Temporary connectivity loss (seconds to hours)
- **Power loss**: Device shutdown, restart with buffered data
- **Maintenance**: Intentional offline periods (firmware updates)
- **Device failures**: Permanent offline (requires replacement)

Without proper offline handling:
- ❌ Can't distinguish "offline" from "idle" (both produce no data)
- ❌ Runtime calculations are wrong (assumes 24/7 operation if ANY messages received)
- ❌ Late-arriving data corrupts aggregates (out-of-order timestamps)
- ❌ No alerts when critical devices go offline
- ❌ Can't calculate uptime SLAs accurately

## Decision Drivers

- **Uptime Accuracy**: Need true uptime % for SLA tracking
- **Alerting**: Detect offline devices within 5 minutes (prevent extended downtime)
- **Data Integrity**: Handle late-arriving data without corrupting aggregates
- **Customer Trust**: Accurate dashboard metrics (wrong uptime = lost credibility)
- **Compliance**: Audit trail of offline events for regulatory requirements

## Decision Outcome

**Chosen strategy**: **Heartbeat + Last-Seen Tracking + Reprocessing Pipeline**

Implement comprehensive offline detection and handling:
1. **Heartbeat messages** (positive signal of device health)
2. **Last-seen tracking** (detect offline within 5 minutes)
3. **Late-data reprocessing** (backfill aggregates when buffered data arrives)
4. **Gap-based runtime calculation** (accurate uptime metrics)
5. **Offline/online events** (audit trail and alerting)

---

## 1. Heartbeat Messages

### Purpose
- Provide **positive signal** that device is alive (vs absence of data = unknown state)
- Enable fast offline detection (within 1-2 missed heartbeats)

### Implementation

**Device sends heartbeat every 60 seconds**, regardless of telemetry activity:

```json
// Heartbeat message (small, always sent)
{
  "message_type": "heartbeat",
  "device_id": "cnc-001-fab-west",
  "customer_id": "acme-manufacturing",
  "timestamp": "2026-02-04T14:00:00Z",
  "status": "online",  // online | idle | error | maintenance
  "uptime_seconds": 86400,
  "firmware_version": "v2.1.3",
  "network_quality": {
    "signal_strength_dbm": -65,
    "packet_loss_pct": 0.1
  }
}
```

**Telemetry messages** (existing, 1/minute during operation):
```json
{
  "message_type": "telemetry",
  "device_id": "cnc-001-fab-west",
  "customer_id": "acme-manufacturing",
  "timestamp": "2026-02-04T14:00:00Z",
  "metrics": {
    "spindle_rpm": 8500,
    "vibration_mm_s": 2.3,
    ...
  }
}
```

### Kafka Topic

**Option 1**: Separate topics (preferred)
```
telemetry (100 partitions, high volume)
heartbeat (20 partitions, low volume, high retention)
```

**Option 2**: Single topic with message_type field
- Simpler, but mixes high/low volume data

**Decision**: Use **separate `heartbeat` topic** for cleaner separation and retention policies.

### Producer Logic

```python
# Device simulator/firmware
import time
from kafka import KafkaProducer

class DeviceClient:
    def __init__(self, device_id, customer_id):
        self.device_id = device_id
        self.customer_id = customer_id
        self.producer = KafkaProducer(...)
        self.uptime_start = time.time()
    
    def start_heartbeat(self):
        # Background thread sends heartbeat every 60s
        while True:
            self.send_heartbeat()
            time.sleep(60)
    
    def send_heartbeat(self):
        message = {
            "message_type": "heartbeat",
            "device_id": self.device_id,
            "customer_id": self.customer_id,
            "timestamp": datetime.utcnow().isoformat(),
            "status": self.get_status(),
            "uptime_seconds": int(time.time() - self.uptime_start)
        }
        self.producer.send('heartbeat', key=self.customer_id, value=message)
```

---

## 2. Last-Seen Tracking

### Purpose
- Track when each device was last seen (heartbeat or telemetry)
- Detect offline state within 5 minutes
- Trigger alerts for critical devices

### Database Table

```sql
CREATE TABLE device_heartbeat (
    device_id VARCHAR(100) PRIMARY KEY,
    customer_id VARCHAR(100) NOT NULL,
    device_type VARCHAR(50),
    
    -- Heartbeat tracking
    last_seen_at TIMESTAMPTZ NOT NULL,
    last_heartbeat_at TIMESTAMPTZ,
    last_telemetry_at TIMESTAMPTZ,
    
    -- Status
    status VARCHAR(20) NOT NULL,  -- online | offline | unknown
    offline_since TIMESTAMPTZ,
    consecutive_missed_heartbeats INT DEFAULT 0,
    
    -- Metadata
    firmware_version VARCHAR(50),
    uptime_seconds BIGINT,
    
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    INDEX idx_customer_status (customer_id, status),
    INDEX idx_offline_devices (status, offline_since) WHERE status = 'offline'
);
```

### Consumer Logic

```python
# Heartbeat consumer (apps/ingestion/heartbeat_consumer.py)
from kafka import KafkaConsumer

consumer = KafkaConsumer('heartbeat', ...)

for message in consumer:
    heartbeat = message.value
    
    # Upsert last-seen tracking
    query = """
        INSERT INTO device_heartbeat (
            device_id, customer_id, device_type,
            last_seen_at, last_heartbeat_at, status,
            firmware_version, uptime_seconds, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, 'online', %s, %s, NOW())
        ON CONFLICT (device_id) DO UPDATE SET
            last_seen_at = EXCLUDED.last_seen_at,
            last_heartbeat_at = EXCLUDED.last_heartbeat_at,
            status = 'online',
            offline_since = NULL,
            consecutive_missed_heartbeats = 0,
            firmware_version = EXCLUDED.firmware_version,
            uptime_seconds = EXCLUDED.uptime_seconds,
            updated_at = NOW()
    """
    execute_query(query, (
        heartbeat['device_id'],
        heartbeat['customer_id'],
        heartbeat.get('device_type'),
        heartbeat['timestamp'],
        heartbeat['timestamp'],
        heartbeat.get('firmware_version'),
        heartbeat.get('uptime_seconds')
    ))
```

### Offline Detection (Periodic Job)

**Airflow DAG**: `detect_offline_devices` (runs every 2 minutes)

```python
from airflow import DAG
from airflow.operators.postgres_operator import PostgresOperator

dag = DAG('detect_offline_devices', schedule_interval='*/2 * * * *', ...)

# Mark devices as offline if no heartbeat in last 5 minutes
detect_offline = PostgresOperator(
    task_id='mark_offline',
    sql="""
        UPDATE device_heartbeat
        SET 
            status = 'offline',
            offline_since = CASE 
                WHEN status != 'offline' THEN NOW() 
                ELSE offline_since 
            END,
            consecutive_missed_heartbeats = consecutive_missed_heartbeats + 1,
            updated_at = NOW()
        WHERE last_seen_at < NOW() - INTERVAL '5 minutes'
          AND status != 'offline'
        RETURNING device_id, customer_id, offline_since;
    """,
    dag=dag
)

# Generate offline events for newly offline devices
generate_events = PythonOperator(
    task_id='generate_offline_events',
    python_callable=generate_offline_events_func,
    dag=dag
)

detect_offline >> generate_events
```

**Event Generation**:
```python
def generate_offline_events_func(**context):
    # For each newly offline device, publish event to Kafka
    offline_devices = context['ti'].xcom_pull(task_ids='mark_offline')
    
    for device in offline_devices:
        event = {
            "event_id": f"evt-offline-{device['device_id']}-{int(time.time())}",
            "device_id": device['device_id'],
            "customer_id": device['customer_id'],
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "device_offline",
            "severity": "warning",
            "message": f"Device went offline (last seen: {device['offline_since']})",
            "metadata": {
                "offline_since": device['offline_since'],
                "last_seen_at": device.get('last_seen_at')
            }
        }
        kafka_producer.send('events', key=device['customer_id'], value=event)
```

---

## 3. Late-Arriving Data Handling

### Problem

Device buffers telemetry during offline period, sends when reconnected:

```
Timeline:
14:00 - Device goes offline
14:01 - Local buffer: {"timestamp": "14:01:00", "metrics": {...}}
14:02 - Local buffer: {"timestamp": "14:02:00", "metrics": {...}}
...
14:30 - Device back online
14:31 - Sends buffered data to Kafka (30 messages with old timestamps)

Kafka receives at 14:31:
  - Message 1: device_timestamp=14:01, sent_at=14:31 (30 min late!)
  - Message 2: device_timestamp=14:02, sent_at=14:31 (29 min late!)
  - ...
```

**Impact**:
- Bronze layer: Late data written to wrong hourly file (based on `sent_at`)
- Silver layer: Already processed 14:00-14:30 hour, now has NEW data
- Gold layer: Aggregates for 14:00-15:00 are stale (missing 30 records)

### Solution: Dual Timestamps + Reprocessing

#### Step 1: Track Both Timestamps

```json
// Enhanced telemetry message
{
  "device_id": "cnc-001",
  "customer_id": "acme",
  "device_timestamp": "2026-02-04T14:01:00Z",  // When device recorded
  "sent_at": "2026-02-04T14:31:00Z",           // When sent to Kafka
  "is_backfill": true,  // Set by device if buffered data
  "metrics": {...}
}
```

#### Step 2: Bronze Layer - Partition by Device Timestamp

**Path structure**:
```
s3://iot-bronze/telemetry/
  customer_id=acme/
    date=2026-02-04/
      hour=14/  # Based on device_timestamp, not sent_at
        telemetry-14-00-to-14-15.json.gz
        telemetry-14-15-to-14-30.json.gz
        telemetry-14-30-to-14-45.json.gz  # Late data appended here at 14:31
```

**Consumer logic**:
```python
def write_to_bronze(message):
    device_ts = parse_timestamp(message['device_timestamp'])
    sent_ts = parse_timestamp(message['sent_at'])
    
    # Partition based on device_timestamp (actual measurement time)
    path = f"s3://iot-bronze/telemetry/customer_id={message['customer_id']}/date={device_ts.date()}/hour={device_ts.hour}/"
    
    # Flag late data
    if (sent_ts - device_ts).total_seconds() > 600:  # >10 min late
        message['is_late_data'] = True
        message['latency_seconds'] = (sent_ts - device_ts).total_seconds()
    
    write_to_s3(path, message)
```

#### Step 3: Silver Layer - Detect and Reprocess

**Airflow DAG**: `bronze_to_silver_hourly` (enhanced)

```python
@task
def check_for_late_data(hour):
    """Check if we received late data for this hour."""
    query = """
        SELECT COUNT(*) as late_count
        FROM bronze_telemetry_metadata
        WHERE device_timestamp_hour = %s
          AND sent_at > %s  -- Sent after hour ended
          AND is_late_data = true
    """
    result = execute_query(query, (hour, hour + timedelta(hours=1)))
    return result['late_count'] > 0

@task
def process_silver(hour, is_reprocessing=False):
    """Process Bronze → Silver, handle reprocessing."""
    if is_reprocessing:
        # Delete existing Silver data for this hour
        execute_query("DELETE FROM telemetry_silver WHERE timestamp >= %s AND timestamp < %s", 
                      (hour, hour + timedelta(hours=1)))
        
        # Truncate Parquet partition
        delete_s3_partition(f"s3://iot-silver/telemetry/date={hour.date()}/hour={hour.hour}/")
    
    # Read Bronze, transform, write Silver
    spark_job = """
        spark-submit --master k8s://... 
        bronze_to_silver.py 
        --input s3://iot-bronze/telemetry/.../{hour}/
        --output s3://iot-silver/telemetry/...
    """
    run_spark_job(spark_job)

# DAG flow with reprocessing
hour = "{{ ds }}"
has_late_data = check_for_late_data(hour)

if has_late_data:
    process_silver(hour, is_reprocessing=True)
else:
    process_silver(hour, is_reprocessing=False)
```

**Tracking reprocessing**:
```sql
ALTER TABLE telemetry_silver
ADD COLUMN data_version INT DEFAULT 1,
ADD COLUMN reprocessed_at TIMESTAMPTZ;

-- Increment version on reprocessing
UPDATE telemetry_silver
SET data_version = data_version + 1,
    reprocessed_at = NOW()
WHERE timestamp >= %s AND timestamp < %s;
```

#### Step 4: Gold Layer - Invalidate and Recalculate

When Silver is reprocessed, invalidate dependent Gold aggregates:

```python
@task
def invalidate_gold_aggregates(hour):
    """Mark Gold aggregates as stale when Silver is reprocessed."""
    date = hour.date()
    
    # Mark device daily summaries as stale
    execute_query("""
        UPDATE device_daily_summary
        SET needs_reprocessing = true
        WHERE date = %s
    """, (date,))

@task
def recalculate_gold(date):
    """Recalculate Gold aggregates from updated Silver data."""
    # Delete existing aggregates
    execute_query("DELETE FROM device_daily_summary WHERE date = %s", (date,))
    
    # Recalculate from Silver
    execute_query("""
        INSERT INTO device_daily_summary (...)
        SELECT ... FROM telemetry_silver WHERE DATE(timestamp) = %s
        GROUP BY device_id, customer_id, DATE(timestamp)
    """, (date,))
```

---

## 4. Gap-Based Runtime Calculation

### Problem

**Current (WRONG)**:
```sql
-- Assumes 24/7 operation if ANY messages received
runtime_hours = COUNT(*) / 60  -- 1 msg/min = hours
```

This breaks when device is offline:
- Device runs 8am-5pm (9 hours), offline 5pm-8am (15 hours)
- Receives 540 messages (9 hours × 60 msg/hr)
- Calculates runtime = 540 / 60 = 9 hours ✓ (accidentally correct)
- But uptime % = (540 / 1440) × 100 = 37.5% ✗ (should be 100% during operational hours)

### Solution: Window Functions for Gap Detection

```sql
WITH message_gaps AS (
    SELECT 
        device_id,
        customer_id,
        timestamp,
        LEAD(timestamp) OVER (PARTITION BY device_id ORDER BY timestamp) as next_timestamp
    FROM telemetry_silver
    WHERE DATE(timestamp) = CURRENT_DATE
),
runtime_periods AS (
    SELECT
        device_id,
        customer_id,
        timestamp as period_start,
        next_timestamp as period_end,
        EXTRACT(EPOCH FROM (next_timestamp - timestamp)) / 3600 as duration_hours,
        CASE
            WHEN next_timestamp - timestamp <= INTERVAL '5 minutes' THEN 'running'
            WHEN next_timestamp - timestamp <= INTERVAL '2 hours' THEN 'offline'
            ELSE 'extended_offline'  -- >2 hours = maintenance or failure
        END as period_type
    FROM message_gaps
    WHERE next_timestamp IS NOT NULL
)
SELECT
    device_id,
    customer_id,
    
    -- Total runtime (gaps < 5 minutes)
    SUM(CASE WHEN period_type = 'running' THEN duration_hours ELSE 0 END) as runtime_hours,
    
    -- Offline time
    SUM(CASE WHEN period_type IN ('offline', 'extended_offline') THEN duration_hours ELSE 0 END) as offline_hours,
    
    -- Count offline events (gaps > 5 min)
    COUNT(CASE WHEN period_type IN ('offline', 'extended_offline') THEN 1 END) as offline_events,
    
    -- Longest offline period
    MAX(CASE WHEN period_type IN ('offline', 'extended_offline') THEN duration_hours * 60 END) as longest_offline_minutes,
    
    -- Uptime percentage (runtime / (runtime + offline))
    (SUM(CASE WHEN period_type = 'running' THEN duration_hours ELSE 0 END) / 
     NULLIF(SUM(duration_hours), 0)) * 100 as uptime_pct

FROM runtime_periods
GROUP BY device_id, customer_id;
```

### Updated `device_daily_summary` Schema

```sql
CREATE TABLE device_daily_summary (
    device_id VARCHAR(100),
    customer_id VARCHAR(100),
    date DATE,
    
    -- Runtime metrics (gap-based calculation)
    runtime_hours DOUBLE PRECISION,  -- Only periods with gaps < 5 min
    offline_hours DOUBLE PRECISION,  -- Periods with gaps > 5 min
    idle_hours DOUBLE PRECISION,     -- 24 - runtime - offline
    
    -- Uptime (runtime / (runtime + offline) × 100)
    uptime_pct DOUBLE PRECISION,
    
    -- Offline tracking
    offline_events INT,              -- Count of offline periods
    longest_offline_minutes INT,     -- Max offline duration
    total_offline_duration_minutes INT,
    
    ...
);
```

---

## 5. Offline/Online Event Generation

### Purpose
- Audit trail of device connectivity
- Customer-facing notification (email/SMS when critical device offline)
- SLA compliance tracking

### Event Schema

```json
// Device offline event
{
  "event_id": "evt-offline-20260204-140000-cnc001",
  "device_id": "cnc-001",
  "customer_id": "acme",
  "timestamp": "2026-02-04T14:00:00Z",
  "event_type": "device_offline",
  "severity": "warning",
  "message": "CNC Machine went offline (last seen: 14:00:00)",
  "metadata": {
    "last_heartbeat": "2026-02-04T13:59:55Z",
    "consecutive_missed_heartbeats": 5,
    "device_type": "cnc_machine",
    "facility": "fab-west"
  }
}

// Device online event (recovery)
{
  "event_id": "evt-online-20260204-143000-cnc001",
  "device_id": "cnc-001",
  "customer_id": "acme",
  "timestamp": "2026-02-04T14:30:00Z",
  "event_type": "device_online",
  "severity": "info",
  "message": "CNC Machine back online after 30 minutes",
  "metadata": {
    "offline_duration_seconds": 1800,
    "offline_since": "2026-02-04T14:00:00Z",
    "buffered_messages_count": 30,
    "firmware_version": "v2.1.3"
  }
}
```

### Alerting Rules

```yaml
# Prometheus AlertManager
groups:
  - name: device_offline
    rules:
      # Critical devices offline > 5 minutes
      - alert: CriticalDeviceOffline
        expr: |
          device_heartbeat_status{status="offline", device_type="cnc_machine"} == 1
          AND device_heartbeat_offline_duration_seconds > 300
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Critical device {{ $labels.device_id }} offline"
          description: "Device has been offline for {{ $value }}s"
      
      # Fleet-wide offline (>10% of customer devices)
      - alert: FleetWideOutage
        expr: |
          (count by (customer_id) (device_heartbeat_status{status="offline"})
          / count by (customer_id) (device_heartbeat_status)) > 0.1
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "{{ $labels.customer_id }}: >10% devices offline"
```

---

## Monitoring and Dashboards

### Metrics to Track

```promql
# Current offline device count
count(device_heartbeat_status{status="offline"}) by (customer_id)

# Average offline duration (last 24h)
avg(device_heartbeat_offline_duration_seconds) by (device_type)

# Late data events (last hour)
rate(bronze_late_data_messages_total[1h])

# Silver reprocessing events
rate(silver_reprocessing_total[1d])

# Device uptime %
avg(device_daily_summary_uptime_pct) by (customer_id)
```

### Grafana Dashboard Panels

1. **Fleet Health Heatmap**: Customer × Device Type → online/offline status
2. **Offline Duration Distribution**: Histogram of offline durations
3. **Late Data Volume**: Count of late messages per hour (backfill activity)
4. **Top Offline Devices**: Devices with most offline events this week

---

## Implementation Phases

### Phase 1: Heartbeat + Last-Seen (Week 1)
- [x] Add heartbeat topic to Kafka
- [ ] Implement heartbeat consumer
- [ ] Create `device_heartbeat` table
- [ ] Airflow DAG for offline detection

### Phase 2: Offline Events + Alerts (Week 1)
- [ ] Generate offline/online events
- [ ] Prometheus metrics and alerts
- [ ] Grafana dashboard

### Phase 3: Late Data Handling (Week 2)
- [ ] Add `sent_at` timestamp to messages
- [ ] Bronze partitioning by `device_timestamp`
- [ ] Silver reprocessing logic
- [ ] Gold invalidation and recalculation

### Phase 4: Gap-Based Runtime (Week 2)
- [ ] Update Silver → Gold aggregation SQL
- [ ] Add offline_hours, offline_events to daily summary
- [ ] Update customer dashboards with uptime %

---

## Consequences

**Good**:
- ✅ Accurate uptime calculations (critical for SLAs)
- ✅ Fast offline detection (<5 minutes, vs hours without heartbeat)
- ✅ Late data handled gracefully (reprocessing, not corruption)
- ✅ Audit trail of offline events (compliance, customer trust)
- ✅ Proactive alerting (prevent extended downtime)

**Bad**:
- ⚠️ Increased Kafka volume (~2x: telemetry + heartbeat)
- ⚠️ Reprocessing complexity (invalidate → recalculate pipeline)
- ⚠️ Storage cost (~10% increase for heartbeat retention)

**Neutral**:
- Silver reprocessing is rare (only when late data arrives, typically <1% of hours)
- Cost: Heartbeat adds ~$20/month for 10k devices (negligible)

---

## Alternatives Considered

### Option 1: No Heartbeat (Absence = Offline)
- ❌ Can't distinguish offline from idle
- ❌ Slow detection (need to wait for multiple missed telemetry)

### Option 2: Heartbeat Only (No Telemetry Timestamp Tracking)
- ⚠️ Can't detect late data (corrupts aggregates)

### Option 3: Always Reprocess Everything
- ❌ Expensive (reprocess all hours every day)
- ❌ Slow (unnecessary work)

**Verdict**: Heartbeat + Last-Seen + Selective Reprocessing is the best balance

---

## More Information

- IoT device connectivity patterns: https://aws.amazon.com/iot-core/features/
- Late-arriving data handling: https://www.databricks.com/blog/handling-late-arriving-data-delta-lake
- Related ADRs:
  - ADR-004: Kafka Partitioning
  - ADR-005: Data Lakehouse Architecture
