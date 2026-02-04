# ADR-005: Data Lakehouse Architecture (Bronze/Silver/Gold)

**Status**: Accepted

**Date**: 2026-02-04

**Deciders**: Platform Team

**Technical Story**: Define data layering strategy for IoT telemetry processing, analytics, and ML feature engineering.

## Context and Problem Statement

We ingest high-volume IoT telemetry (1M+ messages/day) and need to:
1. **Preserve raw data** for audit trail, debugging, and reprocessing
2. **Clean and enrich** data for reliable analytics
3. **Pre-aggregate** metrics for fast dashboards and ML features

Without layering:
- ❌ Raw data mixed with cleaned data (hard to debug)
- ❌ No reprocessing capability (upstream bugs corrupt everything)
- ❌ Slow queries (real-time aggregation on raw data)
- ❌ Unclear data quality (which tables are "source of truth"?)

## Decision Drivers

- **Data Quality**: Separate raw (as-is) from clean (validated)
- **Reprocessability**: Can replay/reprocess from Bronze if bugs found
- **Performance**: Pre-computed aggregates for sub-second dashboards
- **Cost**: Tiered storage (hot/warm/cold) to minimize costs
- **Compliance**: Immutable audit trail for regulatory requirements

## Decision Outcome

**Chosen pattern**: **Medallion Architecture** (Bronze → Silver → Gold)

Inspired by Databricks Delta Lake pattern, adapted for IoT telemetry.

### Layer Definitions

```
Kafka → Bronze (raw) → Silver (cleaned) → Gold (aggregated)
```

---

## Bronze Layer: Raw, Immutable Data

### Purpose
- Preserve **exact** data as ingested from Kafka
- Immutable audit trail (compliance, debugging, reprocessing)
- Includes duplicates, nulls, malformed records

### Storage
- **Format**: JSON (gzipped)
- **Location**: MinIO/S3 (object storage)
- **Partitioning**: `customer_id` / `date` / `hour`

### Path Structure
```
s3://iot-bronze/
  telemetry/
    customer_id=acme-manufacturing/
      date=2026-02-04/
        hour=13/
          telemetry-2026-02-04-13-00.json.gz
          telemetry-2026-02-04-13-15.json.gz
          telemetry-2026-02-04-13-30.json.gz
          telemetry-2026-02-04-13-45.json.gz
  events/
    customer_id=acme-manufacturing/
      date=2026-02-04/
        hour=13/
          events-2026-02-04-13-00.json.gz
```

### Example Data
```json
// Exactly as received, including issues
{"device_id": "cnc-001", "customer_id": "acme", "timestamp": "2026-02-04T13:55:00Z", "metrics": {"vibration_mm_s": 2.3}}
{"device_id": "cnc-001", "customer_id": "acme", "timestamp": "2026-02-04T13:55:00Z", "metrics": {"vibration_mm_s": 2.3}}  // duplicate
{"device_id": null, "customer_id": "acme", "timestamp": null, "metrics": null}  // malformed
{"device_id": "cnc-002", "customer_id": "acme", "timestamp": "2026-02-04T13:55:10Z", "metrics": {"vibration_mm_s": 999}}  // outlier
```

### Retention
- **Policy**: 90 days (compliance requirement)
- **Cost**: ~$0.023/GB/month (S3 Standard)
- **Compression**: 5:1 ratio (JSON → gzip)

### Airflow DAG
- **Name**: `kafka_to_bronze`
- **Schedule**: Continuous (Kafka consumer)
- **Logic**: Read from Kafka, write to S3 (no transformation)

---

## Silver Layer: Cleaned, Validated Data

### Purpose
- **Production-ready** data for analytics and ML
- Deduplication, schema validation, enrichment
- Source of truth for business queries

### Storage
- **Format**: Parquet (columnar, compressed)
- **Location**: S3 (analytics) + Postgres (operational queries)
- **Partitioning**: `customer_id` / `date`

### Path Structure
```
s3://iot-silver/
  telemetry/
    customer_id=acme-manufacturing/
      date=2026-02-04/
        part-00000.parquet
        part-00001.parquet
        ...
```

### Transformations Applied

1. **Deduplication**
   ```sql
   -- Remove exact duplicates based on (device_id, timestamp)
   SELECT DISTINCT ON (device_id, timestamp) *
   FROM bronze_telemetry
   ```

2. **Schema Validation**
   ```python
   # Drop records missing required fields
   df = df.dropna(subset=['device_id', 'customer_id', 'timestamp'])
   
   # Enforce types
   df['timestamp'] = pd.to_datetime(df['timestamp'])
   df['vibration_mm_s'] = pd.to_numeric(df['vibration_mm_s'], errors='coerce')
   ```

3. **Outlier Removal**
   ```python
   # Business rules: physically impossible values
   df = df[df['temperature_c'] <= 500]  # Above boiling point of lead
   df = df[df['vibration_mm_s'] <= 50]  # Severe damage threshold
   df = df[df['power_kw'] >= 0]  # No negative power
   ```

4. **Enrichment**
   ```python
   # Join with device registry for metadata
   df = df.merge(
       device_registry[['device_id', 'model', 'firmware_version', 'facility', 'zone']],
       on='device_id',
       how='left'
   )
   ```

5. **Data Quality Score**
   ```python
   # Calculate quality score per record
   df['data_quality_score'] = (
       (df['vibration_mm_s'].notna()).astype(int) +
       (df['temperature_c'].notna()).astype(int) +
       (df['power_kw'].notna()).astype(int)
   ) / 3.0
   ```

### Schema (Parquet)
```python
{
    "device_id": "string",
    "customer_id": "string",
    "timestamp": "timestamp",
    "device_type": "string",
    "model": "string",
    "firmware_version": "string",
    "facility": "string",
    "zone": "string",
    "spindle_rpm": "double",
    "tool_temperature_c": "double",
    "vibration_mm_s": "double",
    "power_kw": "double",
    "cycle_count": "int64",
    "data_quality_score": "double"
}
```

### Postgres Table (for operational queries)
```sql
CREATE TABLE telemetry_silver (
    id BIGSERIAL PRIMARY KEY,
    device_id VARCHAR(100) NOT NULL,
    customer_id VARCHAR(100) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    device_type VARCHAR(50),
    model VARCHAR(100),
    firmware_version VARCHAR(50),
    facility VARCHAR(100),
    zone VARCHAR(100),
    spindle_rpm DOUBLE PRECISION,
    tool_temperature_c DOUBLE PRECISION,
    vibration_mm_s DOUBLE PRECISION,
    power_kw DOUBLE PRECISION,
    cycle_count INTEGER,
    data_quality_score DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    INDEX idx_device_ts (device_id, timestamp DESC),
    INDEX idx_customer_ts (customer_id, timestamp DESC)
) PARTITION BY RANGE (timestamp);

-- Monthly partitions for efficient pruning
CREATE TABLE telemetry_silver_2026_02 PARTITION OF telemetry_silver
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
```

### Retention
- **Parquet (S3)**: 1 year
- **Postgres**: 90 days (hot data), older data in S3
- **Cost**: ~$0.023/GB/month  (S3) + ~$0.10/GB/month (Postgres)

### Airflow DAG
- **Name**: `bronze_to_silver_hourly`
- **Schedule**: Every hour at :05
- **Logic**: PySpark job reading Bronze JSON, applying transformations, writing Parquet + Postgres

---

## Gold Layer: Business Metrics & Aggregates

### Purpose
- **Pre-computed** metrics for fast dashboards (<100ms queries)
- ML feature engineering (rolling statistics, trends)
- Customer-facing analytics (health scores, cost savings)

### Storage
- **Format**: Postgres tables (optimized for queries)
- **Location**: Postgres (hot), S3 Parquet (cold)

### Tables

#### 1. Device Daily Summary
```sql
CREATE TABLE device_daily_summary (
    device_id VARCHAR(100) NOT NULL,
    customer_id VARCHAR(100) NOT NULL,
    date DATE NOT NULL,
    device_type VARCHAR(50),
    model VARCHAR(100),
    facility VARCHAR(100),
    
    -- Runtime metrics
    runtime_hours DOUBLE PRECISION,
    uptime_pct DOUBLE PRECISION,
    cycle_count INTEGER,
    
    -- Health metrics (aggregates from Silver)
    avg_vibration_mm_s DOUBLE PRECISION,
    max_vibration_mm_s DOUBLE PRECISION,
    p95_vibration_mm_s DOUBLE PRECISION,
    avg_temperature_c DOUBLE PRECISION,
    max_temperature_c DOUBLE PRECISION,
    
    -- Energy metrics
    total_energy_kwh DOUBLE PRECISION,
    avg_power_kw DOUBLE PRECISION,
    peak_power_kw DOUBLE PRECISION,
    
    -- Anomaly counts
    vibration_anomalies INTEGER,
    temperature_anomalies INTEGER,
    error_count INTEGER,
    
    -- Calculated health score (0-100)
    health_score DOUBLE PRECISION,
    health_trend VARCHAR(20),  -- improving | stable | degrading
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (device_id, date)
);
```

**Population Query** (Airflow DAG):
```sql
INSERT INTO device_daily_summary
SELECT 
    device_id,
    customer_id,
    DATE(timestamp) as date,
    MAX(device_type) as device_type,
    MAX(model) as model,
    MAX(facility) as facility,
    
    -- Runtime (sum of 1-minute intervals = hours)
    COUNT(*) / 60.0 as runtime_hours,
    (COUNT(*) / (24.0 * 60.0)) * 100 as uptime_pct,
    MAX(cycle_count) - MIN(cycle_count) as cycle_count,
    
    -- Health metrics
    AVG(vibration_mm_s) as avg_vibration_mm_s,
    MAX(vibration_mm_s) as max_vibration_mm_s,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY vibration_mm_s) as p95_vibration_mm_s,
    AVG(tool_temperature_c) as avg_temperature_c,
    MAX(tool_temperature_c) as max_temperature_c,
    
    -- Energy (sum of kW over 1-min intervals / 60 = kWh)
    SUM(power_kw) / 60.0 as total_energy_kwh,
    AVG(power_kw) as avg_power_kw,
    MAX(power_kw) as peak_power_kw,
    
    -- Anomalies (count of threshold breaches)
    SUM(CASE WHEN vibration_mm_s > 2.0 THEN 1 ELSE 0 END) as vibration_anomalies,
    SUM(CASE WHEN tool_temperature_c > 80 THEN 1 ELSE 0 END) as temperature_anomalies,
    0 as error_count,  -- TODO: join with events table
    
    -- Health score (100 - penalties)
    GREATEST(0, 100 - 
        (SUM(CASE WHEN vibration_mm_s > 2.0 THEN 1 ELSE 0 END) / 10.0) -
        (SUM(CASE WHEN tool_temperature_c > 80 THEN 1 ELSE 0 END) / 10.0)
    ) as health_score,
    
    'stable' as health_trend,  -- TODO: compare with previous day
    
    NOW() as created_at
FROM telemetry_silver
WHERE DATE(timestamp) = CURRENT_DATE - INTERVAL '1 day'
GROUP BY device_id, customer_id, DATE(timestamp);
```

#### 2. Customer Fleet Rollup
```sql
CREATE TABLE customer_daily_rollup (
    customer_id VARCHAR(100) NOT NULL,
    date DATE NOT NULL,
    
    -- Fleet health
    total_devices INTEGER,
    devices_operational INTEGER,  -- health_score >= 80
    devices_warning INTEGER,      -- 60 <= health_score < 80
    devices_critical INTEGER,     -- health_score < 60
    devices_offline INTEGER,
    
    -- Aggregate energy
    total_energy_kwh DOUBLE PRECISION,
    energy_cost_usd DOUBLE PRECISION,  -- Assuming $0.12/kWh
    
    -- Maintenance
    predictive_alerts INTEGER,
    maintenance_events INTEGER,
    unplanned_downtime_hours DOUBLE PRECISION,
    
    -- Cost savings (vs reactive maintenance)
    estimated_savings_usd DOUBLE PRECISION,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (customer_id, date)
);
```

#### 3. ML Features (for predictive maintenance)
```sql
CREATE TABLE ml_features_daily (
    device_id VARCHAR(100) NOT NULL,
    date DATE NOT NULL,
    
    -- 7-day rolling statistics
    vibration_mean_7d DOUBLE PRECISION,
    vibration_std_7d DOUBLE PRECISION,
    vibration_trend_7d DOUBLE PRECISION,  -- linear regression slope
    vibration_cv_7d DOUBLE PRECISION,     -- coefficient of variation
    
    temperature_mean_7d DOUBLE PRECISION,
    temperature_std_7d DOUBLE PRECISION,
    
    energy_efficiency_7d DOUBLE PRECISION,  -- cycle_count / energy_kwh
    
    -- Anomaly rate
    anomaly_rate_7d DOUBLE PRECISION,
    
    -- Failure risk (ML model output)
    failure_risk_score DOUBLE PRECISION,  -- 0-1
    days_to_failure_estimate INTEGER,
    model_version VARCHAR(50),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (device_id, date)
);
```

### Retention
- **Gold Tables**: 3 years (ML training, historical reporting)
- **Cost**: ~$0.10/GB/month (Postgres)

### Airflow DAGs
- **Name**: `silver_to_gold_daily`
- **Schedule**: Daily at 01:00 UTC
- **Logic**: Aggregate Silver → populate Gold tables

---

## Data Lifecycle Summary

| Layer | Format | Storage | Retention | Cost/GB/Month | Use Case |
|-------|--------|---------|-----------|---------------|----------|
| **Bronze** | JSON (gzip) | S3 | 90 days | $0.023 | Audit trail, reprocessing |
| **Silver** | Parquet + Postgres | S3 + DB | 1 year | $0.05 | Analytics, ML training |
| **Gold** | Postgres | DB (+S3 backup) | 3 years | $0.10 | Dashboards, reports |

**Example Costs** (1TB raw telemetry/month):
- Bronze (90d): 3TB × $0.023 = $69/month
- Silver (1y): 12TB × $0.05 = $600/month
- Gold (3y): 1TB × $0.10 = $100/month (highly compressed aggregates)
- **Total**: ~$770/month for 1TB/month ingestion

---

## Alternatives Considered

### Option 1: Single Layer (Raw Only)
- ❌ Every query scans raw data (slow)
- ❌ No deduplication (corrupted analytics)
- ❌ No reprocessing (bugs require manual fixes)

### Option 2: Two Layers (Raw + Aggregated)
- ⚠️ Skip Silver → queries on Bronze are slow
- ⚠️ Outliers corrupt Gold aggregates

### Option 3: Four+ Layers (Bronze/Silver/Gold/Platinum)
- ⚠️ Over-engineering for current scale
- ⚠️ Operational complexity

**Verdict**: Three layers (Bronze/Silver/Gold) is the sweet spot

---

## More Information

- Databricks Medallion Architecture: https://www.databricks.com/glossary/medallion-architecture
- Delta Lake best practices: https://docs.delta.io/latest/best-practices.html
- Related ADRs:
  - ADR-004: Kafka Partitioning
  - ADR-008: Hyperscale Architecture
