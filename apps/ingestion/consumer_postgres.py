"""
Postgres Consumer - Telemetry to Silver Layer

Consumes telemetry from Kafka and inserts into Postgres (Silver layer).
"""

import os
import sys
import json
import logging
from kafka import KafkaConsumer
import psycopg2
from psycopg2.extras import execute_batch
from prometheus_client import start_http_server, Counter, Histogram, Gauge

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Prometheus metrics
messages_consumed = Counter('consumer_messages_consumed_total', 'Messages consumed', ['topic'])
messages_inserted = Counter('consumer_messages_inserted_total', 'Messages inserted to DB')
insert_errors = Counter('consumer_insert_errors_total', 'DB insert errors')
insert_duration = Histogram('consumer_insert_duration_seconds', 'DB insert duration')
consumer_lag = Gauge('consumer_lag', 'Consumer lag', ['topic', 'partition'])


class PostgresConsumer:
    """Kafka consumer that writes telemetry to Postgres."""
    
    def __init__(self):
        self.consumer = None
        self.db_conn = None
        self.batch = []
        self.batch_size = 100
        
    def connect_kafka(self):
        """Initialize Kafka consumer."""
        bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
        group_id = os.getenv('CONSUMER_GROUP_ID', 'telemetry-to-postgres')
        
        logger.info(f"Connecting to Kafka: {bootstrap_servers}")
        
        self.consumer = KafkaConsumer(
            'telemetry',
            bootstrap_servers=bootstrap_servers.split(','),
            group_id=group_id,
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        
        logger.info(f"Kafka consumer initialized (group: {group_id})")
    
    def connect_db(self):
        """Initialize Postgres connection."""
        db_host = os.getenv('POSTGRES_HOST', 'localhost')
        db_port = os.getenv('POSTGRES_PORT', '5432')
        db_name = os.getenv('POSTGRES_DB', 'iot_ops')
        db_user = os.getenv('POSTGRES_USER', 'postgres')
        db_password = os.getenv('POSTGRES_PASSWORD', 'postgres')
        
        logger.info(f"Connecting to Postgres: {db_host}:{db_port}/{db_name}")
        
        self.db_conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_password
        )
        self.db_conn.autocommit = False
        
        logger.info("Postgres connection established")
    
    def insert_telemetry(self, telemetry):
        """Insert telemetry record into Postgres."""
        metrics = telemetry.get('metrics', {})
        location = telemetry.get('location', {})
        
        return (
            telemetry['device_id'],
            telemetry['customer_id'],
            telemetry['device_type'],
            telemetry.get('model'),
            telemetry.get('firmware_version'),
            telemetry['timestamp'],
            location.get('facility'),
            location.get('zone'),
            # CNC metrics
            metrics.get('spindle_rpm'),
            metrics.get('tool_temperature_c'),
            metrics.get('vibration_mm_s'),
            metrics.get('feed_rate_mm_min'),
            metrics.get('cycle_count'),
            metrics.get('coolant_level_pct'),
            # Conveyor metrics
            metrics.get('belt_speed_m_s'),
            metrics.get('motor_temperature_c'),
            metrics.get('load_weight_kg'),
            metrics.get('runtime_hours'),
            # HVAC metrics
            metrics.get('air_temperature_c'),
            metrics.get('humidity_pct'),
            metrics.get('compressor_pressure_psi'),
            metrics.get('fan_speed_rpm'),
            metrics.get('filter_life_pct'),
            # Common
            metrics.get('power_kw'),
            telemetry.get('status')
        )
    
    def flush_batch(self):
        """Flush batch of records to database."""
        if not self.batch:
            return
        
        try:
            with insert_duration.time():
                cursor = self.db_conn.cursor()
                
                sql = """
                    INSERT INTO telemetry_silver (
                        device_id, customer_id, device_type, model, firmware_version,
                        timestamp, facility, zone,
                        spindle_rpm, tool_temperature_c, vibration_mm_s, feed_rate_mm_min, cycle_count, coolant_level_pct,
                        belt_speed_m_s, motor_temperature_c, load_weight_kg, runtime_hours,
                        air_temperature_c, humidity_pct, compressor_pressure_psi, fan_speed_rpm, filter_life_pct,
                        power_kw, status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                
                execute_batch(cursor, sql, self.batch)
                self.db_conn.commit()
                
                messages_inserted.inc(len(self.batch))
                logger.info(f"Inserted {len(self.batch)} records to Postgres")
                
                self.batch = []
                
        except Exception as e:
            insert_errors.inc()
            logger.error(f"Error inserting batch: {e}")
            self.db_conn.rollback()
            self.batch = []
    
    def run(self):
        """Main consumer loop."""
        logger.info("Starting Postgres consumer...")
        
        self.connect_kafka()
        self.connect_db()
        
        # Start Prometheus metrics server
        metrics_port = int(os.getenv('METRICS_PORT', '8000'))
        start_http_server(metrics_port)
        logger.info(f"Prometheus metrics exposed on port {metrics_port}")
        
        logger.info("Consuming messages from 'telemetry' topic...")
        
        try:
            for message in self.consumer:
                telemetry = message.value
                messages_consumed.labels(topic='telemetry').inc()
                
                # Add to batch
                self.batch.append(self.insert_telemetry(telemetry))
                
                # Flush when batch full
                if len(self.batch) >= self.batch_size:
                    self.flush_batch()
                
                # Update consumer lag metric
                lag = self.consumer.highwater(message.partition) - message.offset
                consumer_lag.labels(topic='telemetry', partition=message.partition).set(lag)
                
        except KeyboardInterrupt:
            logger.info("Shutting down consumer...")
            self.flush_batch()  # Flush remaining
            self.consumer.close()
            self.db_conn.close()
            logger.info("Consumer stopped")


if __name__ == '__main__':
    consumer = PostgresConsumer()
    consumer.run()
