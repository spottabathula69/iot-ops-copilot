# IoT Device Simulator

**Status**: Phase 1 - Not Yet Implemented

This directory will contain a Go or Python-based IoT device simulator that generates telemetry data and publishes it to Kafka.

## Planned Features (Phase 1)

- Simulate 100-10,000 concurrent devices
- Generate realistic telemetry:
  - Temperature (°C)
  - Vibration (mm/s)
  - Battery level (%)
  - RSSI (signal strength)
  - Error codes
- Configurable device profiles (firmware versions, models)
- Multi-tenant support (tenant_id)
- Kafka producer integration

## Directory Structure (Future)

```
simulator/
├── cmd/
│   └── main.go              # Entry point
├── internal/
│   ├── device/              # Device simulation logic
│   ├── telemetry/           # Telemetry generation
│   └── producer/            # Kafka producer
├── configs/
│   └── devices.yaml         # Device configurations
├── Dockerfile
└── README.md
```

## Usage (Future)

```bash
go run cmd/main.go --devices 1000 --kafka-brokers kafka:9092
```

---

See [Phase 1 Implementation Plan](../../docs/IMPLEMENTATION.md#phase-1) for details.
