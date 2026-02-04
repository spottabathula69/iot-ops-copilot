-- Telemetry Silver Layer Schema
-- Cleaned, validated IoT device telemetry for analytics

CREATE TABLE IF NOT EXISTS telemetry_silver (
    id BIGSERIAL PRIMARY KEY,
    
    -- Device identifiers
    device_id VARCHAR(100) NOT NULL,
    customer_id VARCHAR(100) NOT NULL,
    device_type VARCHAR(50) NOT NULL,
    model VARCHAR(100),
    firmware_version VARCHAR(50),
    
    -- Timestamp
    timestamp TIMESTAMPTZ NOT NULL,
    
    -- Location
    facility VARCHAR(100),
    zone VARCHAR(100),
    
    -- Common metrics (nullable, depends on device type)
    -- CNC Machine
    spindle_rpm DOUBLE PRECISION,
    tool_temperature_c DOUBLE PRECISION,
    vibration_mm_s DOUBLE PRECISION,
    feed_rate_mm_min INTEGER,
    cycle_count INTEGER,
    coolant_level_pct INTEGER,
    
    -- Conveyor Belt
    belt_speed_m_s DOUBLE PRECISION,
    motor_temperature_c DOUBLE PRECISION,
    load_weight_kg DOUBLE PRECISION,
    runtime_hours DOUBLE PRECISION,
    
    -- HVAC
    air_temperature_c DOUBLE PRECISION,
    humidity_pct DOUBLE PRECISION,
    compressor_pressure_psi DOUBLE PRECISION,
    fan_speed_rpm INTEGER,
    filter_life_pct INTEGER,
    
    -- Common
    power_kw DOUBLE PRECISION,
    status VARCHAR(50),
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_telemetry_device_ts ON telemetry_silver(device_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_telemetry_customer_ts ON telemetry_silver(customer_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp ON telemetry_silver(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_telemetry_device_type ON telemetry_silver(device_type);

-- Partitioning (for production, partition by month)
-- CREATE TABLE telemetry_silver_2026_02 PARTITION OF telemetry_silver
--     FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');


-- Device Heartbeat Tracking
-- Tracks last-seen status for offline detection (per ADR-006)

CREATE TABLE IF NOT EXISTS device_heartbeat (
    device_id VARCHAR(100) PRIMARY KEY,
    customer_id VARCHAR(100) NOT NULL,
    device_type VARCHAR(50),
    
    -- Heartbeat tracking
    last_seen_at TIMESTAMPTZ NOT NULL,
    last_heartbeat_at TIMESTAMPTZ,
    last_telemetry_at TIMESTAMPTZ,
    
    -- Status (per ADR-006)
    status VARCHAR(20) NOT NULL DEFAULT 'unknown',
    -- Values: online | offline_planned | offline_unplanned | unknown
    
    offline_since TIMESTAMPTZ,
    offline_reason VARCHAR(100),
    consecutive_missed_heartbeats INTEGER DEFAULT 0,
    
    -- Device metadata
    firmware_version VARCHAR(50),
    uptime_seconds BIGINT,
    facility VARCHAR(100),
    
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_heartbeat_customer_status ON device_heartbeat(customer_id, status);
CREATE INDEX IF NOT EXISTS idx_heartbeat_offline ON device_heartbeat(status, offline_since) WHERE status LIKE 'offline%';
