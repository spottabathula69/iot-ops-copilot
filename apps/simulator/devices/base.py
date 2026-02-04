"""Base device class for all IoT devices."""

import time
from abc import ABC, abstractmethod
from datetime import datetime


class BaseDevice(ABC):
    """Abstract base class for all device simulators."""
    
    def __init__(self, device_id, customer_id, facility, device_type, model):
        """
        Initialize base device.
        
        Args:
            device_id: Unique device identifier
            customer_id: Customer/tenant identifier
            facility: Facility location
            device_type: Type of device (cnc_machine, conveyor, hvac)
            model: Device model/manufacturer
        """
        self.device_id = device_id
        self.customer_id = customer_id
        self.facility = facility
        self.device_type = device_type
        self.model = model
        self.firmware_version = "v2.1.3"
        self.uptime_start = time.time()
    
    @abstractmethod
    def generate_telemetry(self):
        """Generate telemetry message. Must be implemented by subclasses."""
        pass
    
    def generate_heartbeat(self):
        """Generate heartbeat message (common to all devices)."""
        return {
            "message_type": "heartbeat",
            "device_id": self.device_id,
            "customer_id": self.customer_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "status": "online",
            "uptime_seconds": int(time.time() - self.uptime_start),
            "firmware_version": self.firmware_version
        }
    
    def should_generate_event(self, probability=0.05):
        """
        Determine if an event should be generated.
        
        Args:
            probability: Probability of event (0-1)
        
        Returns:
            bool: True if event should be generated
        """
        import random
        return random.random() < probability
