# ADR-006: Device Offline/Online Handling

**Status**: Accepted

**Date**: 2026-02-04

**Deciders**: Platform Team

**Technical Story**: Handle cases where IoT devices go offline (network issues, power loss, maintenance) and later come back online, potentially with buffered/late-arriving data.

## Context and Problem Statement

Industrial equipment devices may experience:
- **Network outages**: Temporary connectivity loss (seconds to hours)
- **Power loss**: Device shutdown, restart with buffered data
- **Planned downtime**: Outside operating hours (nights, weekends, holidays)
- **Scheduled maintenance**: Intentional offline periods (firmware updates, calibration)
- **Device failures**: Permanent offline (requires replacement)

**Key Insight**: Many customers operate equipment on **shifts** (e.g., Mon-Fri 8AM-5PM, or 24/5), not 24/7. Without operating hours:
- ❌ Uptime % is artificially low (includes nights/weekends)
- ❌ Alert fatigue (device "offline" every night when factory closes)
- ❌ SLA violations incorrectly calculated

Without proper offline handling:
- ❌ Can't distinguish "offline" from "idle" (both produce no data)
- ❌ Runtime calculations are wrong (assumes 24/7 operation if ANY messages received)
- ❌ Late-arriving data corrupts aggregates (out-of-order timestamps)
- ❌ No alerts when critical devices go offline
- ❌ Can't calculate uptime SLAs accurately

## Decision Drivers

- **Uptime Accuracy**: Need true uptime % **during operating hours only** for SLA tracking
- **Alerting**: Detect offline devices within 5 minutes during operating hours (no alerts during planned downtime)
- **Planned vs Unplanned Downtime**: Distinguish scheduled maintenance from unexpected failures
- **Data Integrity**: Handle late-arriving data without corrupting aggregates
- **Customer Trust**: Accurate dashboard metrics (wrong uptime = lost credibility)
- **Compliance**: Audit trail of offline events for regulatory requirements

## Decision Outcome

**Chosen strategy**: **Heartbeat + Last-Seen Tracking + Reprocessing Pipeline**

Implement comprehensive offline detection and handling:
1. **Operating hours/schedules** (define when devices are expected to run)
2. **Heartbeat messages** (positive signal of device health)
3. **Last-seen tracking** (detect offline within 5 minutes during operating hours)
4. **Late-data reprocessing** (backfill aggregates when buffered data arrives)
5. **Gap-based runtime calculation** (accurate uptime metrics during operating hours)
6. **Offline/online events** (audit trail and alerting, suppressed during planned downtime)

---

## 1. Operating Hours and Schedules

### Purpose
- Define **when devices are expected to run** (operating hours)
- Distinguish **planned downtime** (outside operating hours) from **unplanned downtime** (failures)
- Calculate accurate uptime % (only during operating hours)
- Suppress alerts during planned downtime (no alert fatigue)

### Configuration Levels

**Per-Device Schedule** (most granular):
```json
// Device metadata
{
  "device_id": "cnc-001",
  "customer_id": "acme",
  "operating_schedule": {
    "timezone": "America/Los_Angeles",
    "schedule_type": "weekly",  // weekly | 24x7 | custom
    "weekly_schedule": {
      "monday": {"start": "08:00", "end": "17:00"},
      "tuesday": {"start": "08:00", "end": "17:00"},
      "wednesday": {"start": "08:00", "end": "17:00"},
      "thursday": {"start": "08:00", "end": "17:00"},
      "friday": {"start": "08:00", "end": "17:00"},
      "saturday": null,  // not operating
      "sunday": null     // not operating
    },
    "holidays": ["2026-12-25", "2026-01-01"]  // override: not operating
  }
}
```

**Per-Facility Schedule** (common):
```json
// Facility-level schedule (all devices in facility inherit)
{
  "facility_id": "fab-west",
  "customer_id": "acme",
  "operating_schedule": {
    "timezone": "America/Los_Angeles",
    "schedule_type": "24x5",  // 24 hours/day, 5 days/week
    "weekly_schedule": {
      "monday": {"start": "00:00", "end": "23:59"},
      "tuesday": {"start": "00:00", "end": "23:59"},
      "wednesday": {"start": "00:00", "end": "23:59"},
      "thursday": {"start": "00:00", "end": "23:59"},
      "friday": {"start": "00:00", "end": "23:59"},
      "saturday": null,
      "sunday": null
    }
  }
}
```

**Default (24x7)**:
```json
// No schedule defined = assume 24x7 operation
{
  "schedule_type": "24x7"
}
```

### Database Schema

```sql
CREATE TABLE operating_schedules (
    id SERIAL PRIMARY KEY,
    entity_type VARCHAR(20) NOT NULL,  -- device | facility | customer
    entity_id VARCHAR(100) NOT NULL,
    customer_id VARCHAR(100) NOT NULL,
    
    -- Schedule definition
    timezone VARCHAR(50) NOT NULL DEFAULT 'UTC',
    schedule_type VARCHAR(20) NOT NULL,  -- 24x7 | weekly | custom
    
    -- Weekly schedule (JSON)
    weekly_schedule JSONB,  
    -- Example: {"monday": {"start": "08:00", "end": "17:00"}, ...}
    
    -- Holiday overrides
    holidays JSONB,  -- ["2026-12-25", "2026-01-01"]
    
    -- Maintenance windows (override operating hours)
    maintenance_windows JSONB,
    -- Example: [{"start": "2026-02-10T14:00:00Z", "end": "2026-02-10T16:00:00Z", "reason": "firmware_update"}]
    
    effective_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    effective_until TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(entity_type, entity_id, effective_from)
);

CREATE INDEX idx_schedules_entity ON operating_schedules(entity_type, entity_id);
CREATE INDEX idx_schedules_customer ON operating_schedules(customer_id);
```

### Helper Function: Is Device Expected to Run?

```python
from datetime import datetime
import pytz

def is_device_expected_to_run(device_id, timestamp):
    """
    Check if device is expected to be running at given timestamp.
    
    Returns:
        (bool, str): (is_expected, reason)
        - (True, "in_operating_hours")
        - (False, "outside_operating_hours")
        - (False, "holiday")
        - (False, "scheduled_maintenance")
    """
    # Get schedule (device-level, fallback to facility-level, fallback to 24x7)
    schedule = get_operating_schedule(device_id)
    
    if schedule['schedule_type'] == '24x7':
        return (True, "24x7_operation")
    
    # Convert timestamp to facility timezone
    tz = pytz.timezone(schedule['timezone'])
    local_time = timestamp.astimezone(tz)
    
    # Check holidays
    if local_time.date().isoformat() in schedule.get('holidays', []):
        return (False, "holiday")
    
    # Check maintenance windows
    for window in schedule.get('maintenance_windows', []):
        if window['start'] <= timestamp <= window['end']:
            return (False, f"scheduled_maintenance: {window['reason']}")
    
    # Check weekly schedule
    day_name = local_time.strftime('%A').lower()
    day_schedule = schedule['weekly_schedule'].get(day_name)
    
    if day_schedule is None:
        return (False, "not_scheduled_day")
    
    # Parse start/end times
    start_time = datetime.strptime(day_schedule['start'], '%H:%M').time()
    end_time = datetime.strptime(day_schedule['end'], '%H:%M').time()
    current_time = local_time.time()
    
    if start_time <= current_time <= end_time:
        return (True, "in_operating_hours")
    else:
        return (False, "outside_operating_hours")
```

### Usage in Offline Detection

```python
# Enhanced offline detection (Airflow DAG)
def detect_offline_devices():
    now = datetime.utcnow()
    
    # Get devices with missed heartbeats
    offline_candidates = query("""
        SELECT device_id, customer_id, last_seen_at
        FROM device_heartbeat
        WHERE last_seen_at < NOW() - INTERVAL '5 minutes'
          AND status = 'online'
    """)
    
    for device in offline_candidates:
        # Check if device is expected to run right now
        is_expected, reason = is_device_expected_to_run(device['device_id'], now)
        
        if is_expected:
            # UNPLANNED downtime - mark offline and alert
            update_device_status(
                device['device_id'], 
                status='offline_unplanned',
                reason=reason
            )
            generate_offline_alert(device)  # Send alert!
        else:
            # PLANNED downtime - mark offline but DO NOT alert
            update_device_status(
                device['device_id'],
                status='offline_planned',
                reason=reason
            )
            # No alert sent (expected behavior)
```

### Updated `device_heartbeat` Table

```sql
ALTER TABLE device_heartbeat
ADD COLUMN status VARCHAR(20) NOT NULL,  
-- Values: online | offline_planned | offline_unplanned | unknown

ADD COLUMN offline_reason VARCHAR(100);
-- Values: outside_operating_hours | holiday | scheduled_maintenance | network_issue | unknown
```

---

## 2. Heartbeat Messages

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
-- Enhanced aggregation with operating hours awareness
WITH operating_hours_today AS (
    -- Calculate expected operating hours for this device today
    SELECT 
        device_id,
        calculate_operating_hours(device_id, CURRENT_DATE) as expected_hours,
        get_operating_periods(device_id, CURRENT_DATE) as operating_periods
    FROM devices
),
message_gaps AS (
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
    
    -- Operating hours (from schedule)
    expected_operating_hours DOUBLE PRECISION,  -- How many hours device should run today
    
    -- Runtime metrics (gap-based calculation, ONLY during operating hours)
    runtime_hours DOUBLE PRECISION,              -- Actual runtime during operating hours
    offline_unplanned_hours DOUBLE PRECISION,    -- Unplanned downtime during operating hours
    offline_planned_hours DOUBLE PRECISION,      -- Planned downtime (outside operating hours)
    idle_hours DOUBLE PRECISION,                 -- Operating hours - runtime - offline_unplanned
    
    -- Uptime % (ONLY during expected operating hours)
    -- Formula: runtime_hours / expected_operating_hours × 100
    uptime_pct DOUBLE PRECISION,
    
    -- SLA uptime (excludes planned maintenance)
    -- Formula: runtime_hours / (expected_operating_hours - planned_maintenance_hours) × 100
    sla_uptime_pct DOUBLE PRECISION,
    
    -- Offline tracking (ONLY during operating hours)
    offline_events_unplanned INT,            -- Count of unplanned offline periods
    offline_events_planned INT,              -- Count of planned maintenance windows
    longest_offline_minutes INT,             -- Max unplanned offline duration
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
