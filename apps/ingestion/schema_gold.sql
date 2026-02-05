-- Gold Layer Analytics Tables
-- These tables store aggregated, analytics-ready data

-- Hourly device health metrics
CREATE TABLE IF NOT EXISTS device_health_hourly (
    id BIGSERIAL PRIMARY KEY,
    device_id VARCHAR(100) NOT NULL,
    customer_id VARCHAR(100) NOT NULL,
    device_type VARCHAR(50),
    hour_start TIMESTAMPTZ NOT NULL,
    avg_spindle_rpm DOUBLE PRECISION,
    avg_temperature DOUBLE PRECISION,
    max_vibration DOUBLE PRECISION,
    avg_power_kw DOUBLE PRECISION,
    cycle_count_delta INTEGER,
    uptime_minutes INTEGER,
    status VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (device_id, hour_start)
);

CREATE INDEX IF NOT EXISTS idx_device_health_customer ON device_health_hourly(customer_id, hour_start DESC);
CREATE INDEX IF NOT EXISTS idx_device_health_device ON device_health_hourly(device_id, hour_start DESC);

COMMENT ON TABLE device_health_hourly IS 'Hourly aggregated device health metrics for analytics';

-- Daily customer metrics
CREATE TABLE IF NOT EXISTS customer_metrics_daily (
    id BIGSERIAL PRIMARY KEY,
    customer_id VARCHAR(100) NOT NULL,
    date DATE NOT NULL,
    device_count INTEGER,
    total_cycles BIGINT,
    avg_uptime_pct DOUBLE PRECISION,
    anomaly_count INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (customer_id, date)
);

CREATE INDEX IF NOT EXISTS idx_customer_metrics_date ON customer_metrics_daily(customer_id, date DESC);

COMMENT ON TABLE customer_metrics_daily IS 'Daily customer KPIs and summary statistics';
