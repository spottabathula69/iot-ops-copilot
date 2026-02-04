"""HVAC (Heating, Ventilation, Air Conditioning) unit simulator."""

import random
import time
from datetime import datetime
from devices.base import BaseDevice


class HVAC(BaseDevice):
    """HVAC unit simulator."""
    
    def __init__(self, device_id, customer_id, facility, model="carrier-30rb"):
        super().__init__(device_id, customer_id, facility, "hvac", model)
        
        # Baseline metrics
        self.air_temp_base = 22.0  # °C (target room temperature)
        self.humidity_base = 50.0  # %
        self.compressor_pressure_base = 250.0  # PSI
        self.power_kw_base = 8.0
        
        # Thresholds
        self.temp_min = 18.0
        self.temp_max = 26.0
        self.pressure_min = 200.0
        self.pressure_max = 300.0
    
    def generate_telemetry(self):
        """Generate realistic HVAC telemetry."""
        # Normal operation
        air_temp = self.air_temp_base + random.gauss(0, 1.5)
        humidity = self.humidity_base + random.gauss(0, 5)
        compressor_pressure = self.compressor_pressure_base + random.gauss(0, 10)
        power_kw = self.power_kw_base + random.gauss(0, 0.5)
        
        # Simulate anomalies
        if random.random() < 0.04:
            # Pressure fluctuation (refrigerant leak, compressor issue)
            compressor_pressure += random.uniform(-50, 50)
        
        if random.random() < 0.03:
            # Temperature out of range (thermostat issue)
            air_temp += random.uniform(-4, 4)
        
        # Other metrics
        fan_speed = random.randint(1200, 1400)  # RPM
        filter_life = random.randint(60, 90)  # % remaining
        
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
                "zone": "main-building-hvac"
            },
            "metrics": {
                "air_temperature_c": round(air_temp, 1),
                "humidity_pct": round(humidity, 1),
                "compressor_pressure_psi": round(compressor_pressure, 1),
                "power_kw": round(power_kw, 1),
                "fan_speed_rpm": fan_speed,
                "filter_life_pct": filter_life
            },
            "status": "operational"
        }
    
    def generate_event(self, telemetry):
        """Generate event if thresholds exceeded."""
        events = []
        metrics = telemetry["metrics"]
        
        # Temperature out of range
        if metrics["air_temperature_c"] < self.temp_min or metrics["air_temperature_c"] > self.temp_max:
            events.append({
                "event_id": f"evt-temp-{self.device_id}-{int(time.time())}",
                "device_id": self.device_id,
                "customer_id": self.customer_id,
                "timestamp": telemetry["timestamp"],
                "event_type": "threshold_breach",
                "severity": "warning",
                "message": f"Air temperature out of range: {metrics['air_temperature_c']}°C (target: {self.temp_min}-{self.temp_max}°C)",
                "error_code": "TEMP_OUT_OF_RANGE_001",
                "metadata": {
                    "metric": "air_temperature_c",
                    "value": metrics["air_temperature_c"],
                    "threshold_min": self.temp_min,
                    "threshold_max": self.temp_max,
                    "recommended_action": "Check thermostat settings, inspect air flow"
                }
            })
        
        # Compressor pressure out of range
        if metrics["compressor_pressure_psi"] < self.pressure_min or metrics["compressor_pressure_psi"] > self.pressure_max:
            events.append({
                "event_id": f"evt-pressure-{self.device_id}-{int(time.time())}",
                "device_id": self.device_id,
                "customer_id": self.customer_id,
                "timestamp": telemetry["timestamp"],
                "event_type": "threshold_breach",
                "severity": "warning",
                "message": f"Compressor pressure abnormal: {metrics['compressor_pressure_psi']} PSI (normal: {self.pressure_min}-{self.pressure_max} PSI)",
                "error_code": "PRESSURE_ABNORMAL_001",
                "metadata": {
                    "metric": "compressor_pressure_psi",
                    "value": metrics["compressor_pressure_psi"],
                    "threshold_min": self.pressure_min,
                    "threshold_max": self.pressure_max,
                    "recommended_action": "Check refrigerant levels, inspect compressor"
                }
            })
        
        # Filter replacement needed
        if metrics["filter_life_pct"] < 20:
            events.append({
                "event_id": f"evt-filter-{self.device_id}-{int(time.time())}",
                "device_id": self.device_id,
                "customer_id": self.customer_id,
                "timestamp": telemetry["timestamp"],
                "event_type": "maintenance_required",
                "severity": "info",
                "message": f"Air filter replacement needed: {metrics['filter_life_pct']}% remaining",
                "error_code": "FILTER_REPLACE_001",
                "metadata": {
                    "metric": "filter_life_pct",
                    "value": metrics["filter_life_pct"],
                    "threshold": 20,
                    "recommended_action": "Schedule filter replacement"
                }
            })
        
        return events if events else None
