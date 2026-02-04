"""
MinIO Consumer - Telemetry to Bronze Layer

Consumes telemetry from Kafka and writes raw JSON to MinIO (Bronze layer).
"""

import os
import json
import logging
from datetime import datetime
from kafka import KafkaConsumer
from minio import Minio
from minio.error import S3Error
from io import BytesIO
from prometheus_client import start_http_server, Counter, Histogram

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Prometheus metrics
messages_consumed = Counter('bronze_messages_consumed_total', 'Messages consumed')
objects_written = Counter('bronze_objects_written_total', 'Objects written to MinIO')
write_errors = Counter('bronze_write_errors_total', 'MinIO write errors')
write_duration = Histogram('bronze_write_duration_seconds', 'MinIO write duration')


class MinIOConsumer:
    """Kafka consumer that writes raw telemetry to MinIO (Bronze layer)."""
    
    def __init__(self):
        self.consumer = None
        self.minio_client = None
        self.bucket_name = 'iot-bronze'
        
    def connect_kafka(self):
        """Initialize Kafka consumer."""
        bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
        group_id = os.getenv('CONSUMER_GROUP_ID', 'telemetry-to-bronze')
        
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
    
    def connect_minio(self):
        """Initialize MinIO client."""
        endpoint = os.getenv('MINIO_ENDPOINT', 'localhost:9000')
        access_key = os.getenv('MINIO_ACCESS_KEY', 'minioadmin')
        secret_key = os.getenv('MINIO_SECRET_KEY', 'minioadmin')
        secure = os.getenv('MINIO_SECURE', 'false').lower() == 'true'
        
        logger.info(f"Connecting to MinIO: {endpoint}")
        
        self.minio_client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure
        )
        
        # Create bucket if not exists
        if not self.minio_client.bucket_exists(self.bucket_name):
            self.minio_client.make_bucket(self.bucket_name)
            logger.info(f"Created bucket: {self.bucket_name}")
        else:
            logger.info(f"Bucket exists: {self.bucket_name}")
    
    def write_to_bronze(self, telemetry):
        """
        Write telemetry to Bronze layer in MinIO.
        
        Path structure: customer_id/date/hour/device_id-timestamp.json
        Example: acme-manufacturing/2026-02-04/14/cnc-001-1706988000.json
        """
        try:
            # Parse timestamp
            ts = datetime.fromisoformat(telemetry['timestamp'].replace('Z', '+00:00'))
            
            # Build path (partitioned by customer, date, hour)
            object_name = f"{telemetry['customer_id']}/{ts.date()}/{ts.hour:02d}/{telemetry['device_id']}-{int(ts.timestamp())}.json"
            
            # Convert to JSON bytes
            data = json.dumps(telemetry, indent=2).encode('utf-8')
            data_stream = BytesIO(data)
            
            # Write to MinIO
            with write_duration.time():
                self.minio_client.put_object(
                    bucket_name=self.bucket_name,
                    object_name=object_name,
                    data=data_stream,
                    length=len(data),
                    content_type='application/json'
                )
            
            objects_written.inc()
            logger.debug(f"Wrote: {object_name}")
            
        except S3Error as e:
            write_errors.inc()
            logger.error(f"MinIO error: {e}")
        except Exception as e:
            write_errors.inc()
            logger.error(f"Error writing to Bronze: {e}")
    
    def run(self):
        """Main consumer loop."""
        logger.info("Starting Bronze consumer...")
        
        self.connect_kafka()
        self.connect_minio()
        
        # Start Prometheus metrics server
        metrics_port = int(os.getenv('METRICS_PORT', '8001'))
        start_http_server(metrics_port)
        logger.info(f"Prometheus metrics exposed on port {metrics_port}")
        
        logger.info("Consuming messages from 'telemetry' topic...")
        
        try:
            for message in self.consumer:
                telemetry = message.value
                messages_consumed.inc()
                
                # Write to Bronze layer
                self.write_to_bronze(telemetry)
                
        except KeyboardInterrupt:
            logger.info("Shutting down consumer...")
            self.consumer.close()
            logger.info("Consumer stopped")


if __name__ == '__main__':
    consumer = MinIOConsumer()
    consumer.run()
