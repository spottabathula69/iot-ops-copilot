"""Conveyor belt device simulator."""

import random
import time
from datetime import datetime
from devices.base import BaseDevice


class Conveyor(BaseDevice):
    """Conveyor belt system simulator."""
    
    def __init__(self, device_id, customer_id, facility, model="flexlink-xs"):
        super().__init__(device_id, customer_id, facility, "conveyor", model)
        
        # Baseline metrics
        self.belt_speed_base = 1.5  # m/s
        self.motor_temp_base = 65.0  # °C
        self.load_weight_base = 150.0  # kg
        self.runtime_hours = 0
        
        # Thresholds
        self.motor_temp_threshold = 80.0  # °C
        self.overload_threshold = 200.0  # kg
    
    def generate_telemetry(self):
        """Generate realistic conveyor telemetry."""
        # Normal operation
        belt_speed = self.belt_speed_base + random.gauss(0, 0.05)
        motor_temp = self.motor_temp_base + random.gauss(0, 2)
        load_weight = self.load_weight_base + random.gauss(0, 20)
        power_kw = 2.5 + (load_weight / 100) * 0.5  # Power increases with load
        
        # Simulate anomalies
        if random.random() < 0.03:
            # Motor overheating
            motor_temp += random.uniform(10, 20)
        
        if random.random() < 0.02:
            # Overload
            load_weight += random.uniform(50, 100)
        
        # Accumulate runtime (1 minute per telemetry)
        self.runtime_hours += 1 / 60.0
        
        return {
            "message_type": "telemetry",
            "device_id": self.device_id,
            "customer_id": self.customer_id,
            "tenant_id": self.customer_id,
            "device_type": self.device_type,
            "model": self.model,
            "firmware_version": self.firmware_version,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "location": {
                "facility": self.facility,
                "zone": "warehouse-floor-2"
            },
            "metrics": {
                "belt_speed_m_s": round(belt_speed, 2),
                "motor_temperature_c": round(motor_temp, 1),
                "load_weight_kg": round(load_weight, 1),
                "power_kw": round(power_kw, 1),
                "runtime_hours": round(self.runtime_hours, 2),
                "vibration_mm_s": round(random.uniform(0.8, 1.2), 2)
            },
            "status": "operational"
        }
    
    def generate_event(self, telemetry):
        """Generate event if thresholds exceeded."""
        events = []
        metrics = telemetry["metrics"]
        
        # Motor overheating
        if metrics["motor_temperature_c"] > self.motor_temp_threshold:
            events.append({
                "event_id": f"evt-temp-{self.device_id}-{int(time.time())}",
                "device_id": self.device_id,
                "customer_id": self.customer_id,
                "timestamp": telemetry["timestamp"],
                "event_type": "threshold_breach",
                "severity": "warning",
                "message": f"Motor temperature high: {metrics['motor_temperature_c']}°C (limit: {self.motor_temp_threshold}°C)",
                "error_code": "MOTOR_TEMP_HIGH_001",
                "metadata": {
                    "metric": "motor_temperature_c",
                    "value": metrics["motor_temperature_c"],
                    "threshold": self.motor_temp_threshold,
                    "recommended_action": "Reduce belt speed, check motor ventilation"
                }
            })
        
        # Overload
        if metrics["load_weight_kg"] > self.overload_threshold:
            events.append({
                "event_id": f"evt-overload-{self.device_id}-{int(time.time())}",
                "device_id": self.device_id,
                "customer_id": self.customer_id,
                "timestamp": telemetry["timestamp"],
                "event_type": "overload",
                "severity": "warning",
                "message": f"Conveyor overloaded: {metrics['load_weight_kg']}kg (limit: {self.overload_threshold}kg)",
                "error_code": "OVERLOAD_001",
                "metadata": {
                    "metric": "load_weight_kg",
                    "value": metrics["load_weight_kg"],
                    "threshold": self.overload_threshold,
                    "recommended_action": "Remove excess load, check belt tension"
                }
            })
        
        return events if events else None
