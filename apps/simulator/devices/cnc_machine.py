"""CNC Machine device simulator."""

import random
import time
from datetime import datetime
from devices.base import BaseDevice


class CNCMachine(BaseDevice):
    """CNC (Computer Numerical Control) machine simulator."""
    
    def __init__(self, device_id, customer_id, facility, model="haas-vf2"):
        super().__init__(device_id, customer_id, facility, "cnc_machine", model)
        
        # Baseline metrics (normal operation)
        self.spindle_rpm_base = 8000
        self.tool_temp_base = 75.0
        self.vibration_base = 1.5
        self.power_kw_base = 12.0
        self.cycle_count = 0
        
        # Thresholds (for event generation)
        self.vibration_threshold = 2.0  # mm/s
        self.temperature_threshold = 85.0  # °C
   
    def generate_telemetry(self):
        """
        Generate realistic CNC telemetry with variance and occasional anomalies.
        
        Returns:
            dict: Telemetry message
        """
        # Normal operation with Gaussian noise
        spindle_rpm = self.spindle_rpm_base + random.gauss(0, 200)
        tool_temp = self.tool_temp_base + random.gauss(0, 3)
        vibration = self.vibration_base + random.gauss(0, 0.2)
        power_kw = self.power_kw_base + random.gauss(0, 1)
        
        # Simulate anomalies (5% chance)
        if random.random()< 0.05:
            # Vibration spike (tool wear, imbalance)
            vibration += random.uniform(0.5, 1.5)
        
        if random.random() < 0.03:
            # Temperature spike (coolant issue)
            tool_temp += random.uniform(5, 15)
        
        # Increment cycle count
        self.cycle_count += 1
        
        # Other metrics
        feed_rate = random.randint(400, 500)  # mm/min
        coolant_level = random.randint(80, 95)  # %
        
        return {
            "message_type": "telemetry",
            "device_id": self.device_id,
            "customer_id": self.customer_id,
            "tenant_id": self.customer_id,  # For multi-tenancy
            "device_type": self.device_type,
            "model": self.model,
            "firmware_version": self.firmware_version,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "location": {
                "facility": self.facility,
                "zone": "production-line-3",
                "coordinates": {"lat": 37.7749, "lon": -122.4194}
            },
            "metrics": {
                "spindle_rpm": round(spindle_rpm, 1),
                "tool_temperature_c": round(tool_temp, 1),
                "vibration_mm_s": round(vibration, 2),
                "power_kw": round(power_kw, 1),
                "cycle_count": self.cycle_count,
                "feed_rate_mm_min": feed_rate,
                "coolant_level_pct": coolant_level
            },
            "status": "operational"
        }
    
    def generate_event(self, telemetry):
        """
        Generate event if thresholds exceeded.
        
        Args:
            telemetry: Telemetry message to check
        
        Returns:
            dict or None: Event message if threshold breached
        """
        events = []
        metrics = telemetry["metrics"]
        
        # Vibration threshold breach
        if metrics["vibration_mm_s"] > self.vibration_threshold:
            events.append({
                "event_id": f"evt-vib-{self.device_id}-{int(time.time())}",
                "device_id": self.device_id,
                "customer_id": self.customer_id,
                "timestamp": telemetry["timestamp"],
                "event_type": "threshold_breach",
                "severity": "warning",
                "message": f"Vibration exceeded threshold: {metrics['vibration_mm_s']}mm/s (limit: {self.vibration_threshold}mm/s)",
                "error_code": "VIB_HIGH_001",
                "metadata": {
                    "metric": "vibration_mm_s",
                    "value": metrics["vibration_mm_s"],
                    "threshold": self.vibration_threshold,
                    "recommended_action": "Inspect tool balance, check spindle bearings"
                }
            })
        
        # Temperature threshold breach
        if metrics["tool_temperature_c"] > self.temperature_threshold:
            events.append({
                "event_id": f"evt-temp-{self.device_id}-{int(time.time())}",
                "device_id": self.device_id,
                "customer_id": self.customer_id,
                "timestamp": telemetry["timestamp"],
                "event_type": "threshold_breach",
                "severity": "warning",
                "message": f"Tool temperature exceeded threshold: {metrics['tool_temperature_c']}°C (limit: {self.temperature_threshold}°C)",
                "error_code": "TEMP_HIGH_001",
                "metadata": {
                    "metric": "tool_temperature_c",
                    "value": metrics["tool_temperature_c"],
                    "threshold": self.temperature_threshold,
                    "recommended_action": "Check coolant flow, reduce cutting speed"
                }
            })
        
        return events if events else None
