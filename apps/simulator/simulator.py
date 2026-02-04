"""
IoT Device Simulator - Main Orchestrator

Simulates industrial equipment sending telemetry, heartbeats, and events to Kafka.
"""

import os
import sys
import time
import yaml
import logging
import argparse
from threading import Thread
from kafka import KafkaProducer
from prometheus_client import start_http_server, Counter, Gauge
import json

# Import device simulators
from devices import CNCMachine, Conveyor, HVAC


# Prometheus metrics
messages_sent = Counter('simulator_messages_sent_total', 'Total messages sent', ['topic', 'device_type'])
devices_total = Gauge('simulator_devices_total', 'Number of simulated devices', ['customer', 'facility'])
errors_total = Counter('simulator_errors_total', 'Error count', ['type'])

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DeviceSimulator:
    """Main simulator orchestrator."""
    
    def __init__(self, config_file):
        """Initialize simulator with configuration."""
        self.config = self.load_config(config_file)
        self.devices = []
        self.producer = None
        self.running = False
        
    def load_config(self, config_file):
        """Load YAML configuration."""
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        logger.info(f"Loaded configuration from {config_file}")
        return config
    
    def setup_kafka(self):
        """Initialize Kafka producer."""
        bootstrap_servers = os.getenv(
            'KAFKA_BOOTSTRAP_SERVERS',
            self.config['simulator']['kafka_bootstrap_servers']
        )
        
        logger.info(f"Connecting to Kafka: {bootstrap_servers}")
        
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers.split(','),
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None,
            acks='all',  # Wait for all replicas
            retries=3
        )
        
        logger.info("Kafka producer initialized")
    
    def create_devices(self):
        """Create device instances from configuration."""
        device_classes = {
            'cnc_machine': CNCMachine,
            'conveyor': Conveyor,
            'hvac': HVAC
        }
        
        for customer in self.config['customers']:
            customer_id = customer['customer_id']
            
            for facility in customer['facilities']:
                facility_id = facility['facility_id']
                
                for device_config in facility['devices']:
                    device_type = device_config['type']
                    count = device_config['count']
                    model = device_config.get('model', '')
                    
                    device_class = device_classes.get(device_type)
                    if not device_class:
                        logger.warning(f"Unknown device type: {device_type}, skipping")
                        continue
                    
                    # Create multiple instances
                    for i in range(1, count + 1):
                        device_id = f"{device_type}-{i:03d}-{facility_id}"
                        device = device_class(device_id, customer_id, facility_id, model)
                        self.devices.append(device)
                        logger.info(f"Created device: {device_id} ({customer_id})")
                
                # Update Prometheus metric
                device_count = sum(d['count'] for d in facility['devices'])
                devices_total.labels(customer=customer_id, facility=facility_id).set(device_count)
        
        logger.info(f"Total devices created: {len(self.devices)}")
    
    def send_telemetry(self, device):
        """Generate and send telemetry for a device."""
        try:
            # Generate telemetry
            telemetry = device.generate_telemetry()
            
            # Send to Kafka (key = customer_id for partitioning per ADR-004)
            self.producer.send(
                topic='telemetry',
                key=telemetry['customer_id'],
                value=telemetry
            )
            
            messages_sent.labels(topic='telemetry', device_type=device.device_type).inc()
            
            # Check for events
            events = device.generate_event(telemetry)
            if events:
                for event in events:
                    self.producer.send(
                        topic='events',
                        key=event['customer_id'],
                        value=event
                    )
                    messages_sent.labels(topic='events', device_type=device.device_type).inc()
                    logger.info(f"Event generated: {event['event_id']} - {event['message']}")
            
        except Exception as e:
            errors_total.labels(type='telemetry').inc()
            logger.error(f"Error sending telemetry for {device.device_id}: {e}")
    
    def send_heartbeat(self, device):
        """Generate and send heartbeat for a device."""
        try:
            heartbeat = device.generate_heartbeat()
            
            self.producer.send(
                topic='heartbeat',
                key=heartbeat['customer_id'],
                value=heartbeat
            )
            
            messages_sent.labels(topic='heartbeat', device_type=device.device_type).inc()
            
        except Exception as e:
            errors_total.labels(type='heartbeat').inc()
            logger.error(f"Error sending heartbeat for {device.device_id}: {e}")
    
    def telemetry_loop(self):
        """Main telemetry loop (runs every 60 seconds)."""
        interval = int(os.getenv(
            'TELEMETRY_INTERVAL_SECONDS',
            self.config['simulator']['telemetry_interval_seconds']
        ))
        
        while self.running:
            logger.info(f"Sending telemetry for {len(self.devices)} devices...")
            
            for device in self.devices:
                self.send_telemetry(device)
            
            # Flush producer
            self.producer.flush()
            logger.info(f"Telemetry batch sent, sleeping {interval}s")
            
            time.sleep(interval)
    
    def heartbeat_loop(self):
        """Heartbeat loop (runs every 60 seconds)."""
        interval = int(os.getenv(
            'HEARTBEAT_INTERVAL_SECONDS',
            self.config['simulator']['heartbeat_interval_seconds']
        ))
        
        while self.running:
            logger.info(f"Sending heartbeats for {len(self.devices)} devices...")
            
            for device in self.devices:
                self.send_heartbeat(device)
            
            self.producer.flush()
            logger.info(f"Heartbeat batch sent, sleeping {interval}s")
            
            time.sleep(interval)
    
    def start(self):
        """Start the simulator."""
        logger.info("Starting IoT Device Simulator...")
        
        # Setup
        self.setup_kafka()
        self.create_devices()
        
        # Start Prometheus metrics server
        metrics_port = int(os.getenv('METRICS_PORT', self.config['simulator']['metrics_port']))
        start_http_server(metrics_port)
        logger.info(f"Prometheus metrics exposed on port {metrics_port}")
        
        # Start telemetry and heartbeat threads
        self.running = True
        
        telemetry_thread = Thread(target=self.telemetry_loop, daemon=True)
        heartbeat_thread = Thread(target=self.heartbeat_loop, daemon=True)
        
        telemetry_thread.start()
        heartbeat_thread.start()
        
        logger.info("Simulator started successfully")
        
        # Keep main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down simulator...")
            self.running = False
            telemetry_thread.join()
            heartbeat_thread.join()
            self.producer.close()
            logger.info("Simulator stopped")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='IoT Device Simulator')
    parser.add_argument('--config', default='config.yaml', help='Configuration file')
    parser.add_argument('--log-level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'])
    args = parser.parse_args()
    
    # Set log level
    logging.getLogger().setLevel(args.log_level)
    
    # Run simulator
    simulator = DeviceSimulator(args.config)
    simulator.start()


if __name__ == '__main__':
    main()
