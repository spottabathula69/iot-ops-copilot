"""
Silver to Gold Aggregations DAG

Creates aggregated analytics tables from Silver layer telemetry:
- device_health_hourly: Hourly device health metrics
- customer_metrics_daily: Daily customer KPIs

Schedule: Hourly (triggered after bronze_to_silver completes)
Owner: data-team
"""

from airflow import DAG
from airflow.providers.postgres.operators.postgres import PostgresOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'data-team',
    'depends_on_past': False,
    'email_on_failure': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'silver_to_gold_aggregations',
    default_args=default_args,
    description='Aggregate Silver telemetry to Gold analytics tables',
    schedule_interval='15 * * * *',  # Run at :15 past every hour (after bronze_to_silver)
    start_date=datetime(2026, 2, 1),
    catchup=False,
    tags=['etl', 'silver', 'gold', 'aggregation'],
    max_active_runs=1,
)

# Task 1: Create/update hourly device health metrics
device_health_hourly = PostgresOperator(
    task_id='device_health_hourly',
    postgres_conn_id='postgres_iot',
    sql="""
        -- Aggregate hourly device health metrics
        INSERT INTO device_health_hourly (
            device_id,
            customer_id,
            device_type,
            hour_start,
            avg_spindle_rpm,
            avg_temperature,
            max_vibration,
            avg_power_kw,
            cycle_count_delta,
            uptime_minutes,
            status
        )
        SELECT
            device_id,
            customer_id,
            device_type,
            DATE_TRUNC('hour', timestamp) as hour_start,
            AVG(spindle_rpm) as avg_spindle_rpm,
            AVG(COALESCE(tool_temperature_c, motor_temperature_c, air_temperature_c)) as avg_temperature,
            MAX(vibration_mm_s) as max_vibration,
            AVG(power_kw) as avg_power_kw,
            MAX(cycle_count) - MIN(cycle_count) as cycle_count_delta,
            COUNT(*) as uptime_minutes,
            MODE() WITHIN GROUP (ORDER BY status) as status
        FROM telemetry_silver
        WHERE timestamp >= DATE_TRUNC('hour', NOW() - INTERVAL '1 hour')
          AND timestamp < DATE_TRUNC('hour', NOW())
        GROUP BY device_id, customer_id, device_type, DATE_TRUNC('hour', timestamp)
        ON CONFLICT (device_id, hour_start) DO UPDATE
        SET
            avg_spindle_rpm = EXCLUDED.avg_spindle_rpm,
            avg_temperature = EXCLUDED.avg_temperature,
            max_vibration = EXCLUDED.max_vibration,
            avg_power_kw = EXCLUDED.avg_power_kw,
            cycle_count_delta = EXCLUDED.cycle_count_delta,
            uptime_minutes = EXCLUDED.uptime_minutes,
            status = EXCLUDED.status,
            updated_at = NOW();
    """,
    dag=dag,
)

# Task 2: Create/update daily customer metrics
customer_metrics_daily = PostgresOperator(
    task_id='customer_metrics_daily',
    postgres_conn_id='postgres_iot',
    sql="""
        -- Aggregate daily customer KPIs
        INSERT INTO customer_metrics_daily (
            customer_id,
            date,
            device_count,
            total_cycles,
            avg_uptime_pct,
            anomaly_count
        )
        SELECT
            customer_id,
            DATE(hour_start) as date,
            COUNT(DISTINCT device_id) as device_count,
            SUM(cycle_count_delta) as total_cycles,
            AVG(uptime_minutes / 60.0 * 100) as avg_uptime_pct,
            SUM(CASE WHEN max_vibration > 2.0 THEN 1 ELSE 0 END) as anomaly_count
        FROM device_health_hourly
        WHERE DATE(hour_start) >= CURRENT_DATE - 1
          AND DATE(hour_start) < CURRENT_DATE
        GROUP BY customer_id, DATE(hour_start)
        ON CONFLICT (customer_id, date) DO UPDATE
        SET
            device_count = EXCLUDED.device_count,
            total_cycles = EXCLUDED.total_cycles,
            avg_uptime_pct = EXCLUDED.avg_uptime_pct,
            anomaly_count = EXCLUDED.anomaly_count,
            updated_at = NOW();
    """,
    dag=dag,
)

# Task dependencies: device health must complete before customer metrics
device_health_hourly >> customer_metrics_daily
