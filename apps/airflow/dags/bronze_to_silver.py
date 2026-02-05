"""
Bronze to Silver Parquet Transformation DAG

This DAG reads raw JSON telemetry from MinIO Bronze layer,
transforms and cleans the data, and writes Parquet files to Silver layer.

Schedule: Hourly
Owner: data-team
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.providers.postgres.hooks.postgres import PostgresHook
from datetime import datetime, timedelta
import json
import logging

default_args = {
    'owner': 'data-team',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(minutes=30),
}

dag = DAG(
    'bronze_to_silver_parquet',
    default_args=default_args,
    description='Transform Bronze JSON to Silver Parquet',
    schedule_interval='@hourly',
    start_date=datetime(2026, 2, 1),
    catchup=False,
    tags=['etl', 'bronze', 'silver', 'transformation'],
    max_active_runs=1,
)

def process_bronze_to_silver(**context):
    """
    Read JSON from MinIO Bronze, transform to structured format in Postgres Silver.
    
    For this MVP, we'll write directly to Postgres instead of Parquet in MinIO
    to simplify the architecture. Future iteration can add Parquet export.
    """
    execution_date = context['execution_date']
    year = execution_date.year
    month = f"{execution_date.month:02d}"
    day = f"{execution_date.day:02d}"
    hour = f"{execution_date.hour:02d}"
    
    logging.info(f"Processing Bronze data for {year}-{month}-{day} {hour}:00")
    
    # Initialize hooks
    s3_hook = S3Hook(aws_conn_id='minio')
    pg_hook = PostgresHook(postgres_conn_id='postgres_iot')
    
    # List all JSON files for this hour
    bronze_prefix = f"{year}-{month}-{day}/{hour}/"
    
    try:
        # Get S3 client for MinIO
        s3_client = s3_hook.get_conn()
        
        # List objects in Bronze bucket
        response = s3_client.list_objects_v2(
            Bucket='iot-bronze',
            Prefix=bronze_prefix
        )
        
        if 'Contents' not in response:
            logging.info(f"No files found for prefix: {bronze_prefix}")
            return {"files_processed": 0, "records_inserted": 0}
        
        files = [obj['Key'] for obj in response['Contents']]
        logging.info(f"Found {len(files)} files to process")
        
        # Process in batches
        total_records = 0
        records_batch = []
        batch_size = 100
        
        for file_key in files:
            # Read JSON from MinIO
            obj = s3_client.get_object(Bucket='iot-bronze', Key=file_key)
            json_content = obj['Body'].read().decode('utf-8')
            telemetry = json.loads(json_content)
            
            # Extract fields (handle different device types)
            record = {
                'device_id': telemetry.get('device_id'),
                'customer_id': telemetry.get('customer_id'),
                'device_type': telemetry.get('device_type'),
                'model': telemetry.get('model'),
                'firmware_version': telemetry.get('firmware_version'),
                'timestamp': telemetry.get('timestamp'),
                'facility': telemetry.get('location', {}).get('facility'),
                'zone': telemetry.get('location', {}).get('zone'),
                'status': telemetry.get('status'),
            }
            
            # Add metrics (varies by device type)
            metrics = telemetry.get('metrics', {})
            record.update({
                'spindle_rpm': metrics.get('spindle_rpm'),
                'tool_temperature_c': metrics.get('tool_temperature_c'),
                'vibration_mm_s': metrics.get('vibration_mm_s'),
                'power_kw': metrics.get('power_kw'),
                'cycle_count': metrics.get('cycle_count'),
                'feed_rate_mm_min': metrics.get('feed_rate_mm_min'),
                'coolant_level_pct': metrics.get('coolant_level_pct'),
                'belt_speed_m_s': metrics.get('belt_speed_m_s'),
                'motor_temperature_c': metrics.get('motor_temperature_c'),
                'load_weight_kg': metrics.get('load_weight_kg'),
                'runtime_hours': metrics.get('runtime_hours'),
                'air_temperature_c': metrics.get('air_temperature_c'),
                'humidity_pct': metrics.get('humidity_pct'),
                'compressor_pressure_psi': metrics.get('compressor_pressure_psi'),
                'fan_speed_rpm': metrics.get('fan_speed_rpm'),
                'filter_life_pct': metrics.get('filter_life_pct'),
            })
            
            records_batch.append(record)
            
            # Insert batch when full
            if len(records_batch) >= batch_size:
                insert_batch(pg_hook, records_batch)
                total_records += len(records_batch)
                records_batch = []
        
        # Insert remaining records
        if records_batch:
            insert_batch(pg_hook, records_batch)
            total_records += len(records_batch)
        
        logging.info(f"Successfully processed {len(files)} files, inserted {total_records} records")
        
        return {
            "files_processed": len(files),
            "records_inserted": total_records,
            "execution_hour": f"{year}-{month}-{day} {hour}:00"
        }
        
    except Exception as e:
        logging.error(f"Error processing Bronze to Silver: {str(e)}")
        raise

def insert_batch(pg_hook, records):
    """Insert a batch of records into telemetry_silver table."""
    if not records:
        return
    
    # Build INSERT statement
    insert_sql = """
        INSERT INTO telemetry_silver (
            device_id, customer_id, device_type, model, firmware_version,
            timestamp, facility, zone, status,
            spindle_rpm, tool_temperature_c, vibration_mm_s, power_kw, cycle_count,
            feed_rate_mm_min, coolant_level_pct,
            belt_speed_m_s, motor_temperature_c, load_weight_kg, runtime_hours,
            air_temperature_c, humidity_pct, compressor_pressure_psi, fan_speed_rpm, filter_life_pct
        ) VALUES (
            %(device_id)s, %(customer_id)s, %(device_type)s, %(model)s, %(firmware_version)s,
            %(timestamp)s, %(facility)s, %(zone)s, %(status)s,
            %(spindle_rpm)s, %(tool_temperature_c)s, %(vibration_mm_s)s, %(power_kw)s, %(cycle_count)s,
            %(feed_rate_mm_min)s, %(coolant_level_pct)s,
            %(belt_speed_m_s)s, %(motor_temperature_c)s, %(load_weight_kg)s, %(runtime_hours)s,
            %(air_temperature_c)s, %(humidity_pct)s, %(compressor_pressure_psi)s, %(fan_speed_rpm)s, %(filter_life_pct)s
        )
        ON CONFLICT (device_id, timestamp) DO NOTHING;
    """
    
    # Execute batch insert
    conn = pg_hook.get_conn()
    cursor = conn.cursor()
    
    try:
        for record in records:
            cursor.execute(insert_sql, record)
        conn.commit()
    except Exception as e:
        conn.rollback()
        logging.error(f"Batch insert failed: {str(e)}")
        raise
    finally:
        cursor.close()

# Task definition
transform_task = PythonOperator(
    task_id='bronze_to_silver',
    python_callable=process_bronze_to_silver,
    provide_context=True,
    dag=dag,
)
