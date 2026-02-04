# SLO Framework - IoT Ops Copilot

## Overview

Service Level Objectives (SLOs) define target reliability for services. This document establishes the SLO framework, measurement methodology, and error budget tracking for the IoT Ops Copilot platform.

## SLO Principles

1. **User-Centric**: SLOs should reflect actual user experience, not just internal metrics
2. **Achievable**: Targets should be realistic given current architecture and resources
3. **Actionable**: Breaching an SLO should trigger specific investigation/mitigation actions
4. **Measurable**: SLIs (indicators) must be reliably observable via Prometheus/Grafana

## SLO Definitions

### Copilot API Service

**Service Description**: FastAPI backend serving `/ask`, `/insights`, and `/troubleshoot` endpoints.

| SLI | Target | Measurement Window | Error Budget |
|-----|--------|-------------------|--------------|
| **Availability** | 99.5% of requests succeed (non-5xx) | 30 days | 0.5% (216 min/month) |
| **Latency** | 95% of requests complete in < 2s | 30 days | 5% above threshold |
| **Latency (p99)** | 99% of requests complete in < 5s | 30 days | 1% above threshold |

**Measurement**:
```promql
# Availability
sum(rate(http_requests_total{service="copilot-api", code!~"5.."}[5m])) 
/ 
sum(rate(http_requests_total{service="copilot-api"}[5m]))

# Latency (p95)
histogram_quantile(0.95, 
  rate(http_request_duration_seconds_bucket{service="copilot-api"}[5m])
)
```

**Error Budget Alert**:
- **Warning**: 50% of monthly budget consumed
- **Critical**: 80% of monthly budget consumed

---

### RAG Retrieval Service

**Service Description**: Hybrid retrieval (BM25 + vector) with reranking.

| SLI | Target | Measurement Window | Error Budget |
|-----|--------|-------------------|--------------|
| **Availability** | 99.9% of queries succeed | 30 days | 0.1% (43 min/month) |
| **Latency (p95)** | 95% of retrievals in < 500ms | 30 days | 5% above threshold |
| **Quality: Empty Results** | < 5% of queries return zero results | 7 days | 5% |
| **Quality: Citations** | > 90% of answers include citations | 7 days | 10% |

**Measurement**:
```promql
# Availability
sum(rate(rag_retrieval_requests_total{status="success"}[5m])) 
/ 
sum(rate(rag_retrieval_requests_total[5m]))

# Empty results rate
sum(rate(rag_retrieval_requests_total{result_count="0"}[5m])) 
/ 
sum(rate(rag_retrieval_requests_total[5m]))

# Citation ratio
sum(rate(llm_responses_total{has_citations="true"}[5m])) 
/ 
sum(rate(llm_responses_total[5m]))
```

---

### Kafka Ingestion

**Service Description**: Telemetry ingestion via Kafka consumers.

| SLI | Target | Measurement Window | Error Budget |
|-----|--------|-------------------|--------------|
| **Consumer Lag** | < 1000 messages per partition | Real-time | N/A (continuous) |
| **Throughput** | Process 10k msgs/sec (p50) | 5 minutes | 20% degradation |
| **Data Loss** | 0 messages dropped (DLQ < 0.01%) | 30 days | 0.01% |

**Measurement**:
```promql
# Consumer lag
kafka_consumer_lag{topic="telemetry"}

# Throughput
sum(rate(kafka_messages_consumed_total[5m]))

# Dead letter queue rate
sum(rate(kafka_dlq_messages_total[5m])) 
/ 
sum(rate(kafka_messages_consumed_total[5m]))
```

**Alert**:
- **Warning**: Lag > 1000 messages for > 5 minutes
- **Critical**: Lag > 10000 messages for > 2 minutes

---

### Airflow Pipelines

**Service Description**: Data pipeline orchestration (bronze/silver/gold).

| SLI | Target | Measurement Window | Error Budget |
|-----|--------|-------------------|--------------|
| **DAG Success Rate** | > 99% of DAG runs succeed | 30 days | 1% |
| **DAG Duration (p95)** | 95% of `bronze_to_silver` runs finish in < 10 min | 7 days | 5% above threshold |
| **Freshness** | Gold layer data is < 24 hours old | Continuous | 1% staleness |

**Measurement**:
```promql
# Success rate
sum(airflow_dag_run_duration_seconds_count{state="success"}) 
/ 
sum(airflow_dag_run_duration_seconds_count)

# Duration
histogram_quantile(0.95, 
  rate(airflow_dag_run_duration_seconds_bucket{dag_id="bronze_to_silver"}[1h])
)
```

---

## Error Budget Tracking

### Budget Calculation

**Formula**:
```
Error Budget = (1 - SLO) × Total Requests
```

**Example** (Copilot API, 99.5% availability SLO):
- Month with 10M requests
- Error budget = (1 - 0.995) × 10M = 50k failed requests
- If 25k requests fail, 50% of budget consumed

### Budget Burn Rate

**Burn rate** measures how fast you're consuming your error budget.

```
Burn Rate = (Error Rate / (1 - SLO))
```

**Example**:
- Current error rate: 1% (over last hour)
- SLO: 99.5% availability (0.5% allowed error rate)
- Burn rate = 1% / 0.5% = **2x**
  - Burning budget 2x faster than allowed
  - At this rate, entire monthly budget consumed in 15 days

**Alert Thresholds**:
| Burn Rate | Window | Severity | Action |
|-----------|--------|----------|--------|
| 14x | 1 hour | Critical | Page on-call immediately |
| 7x | 6 hours | High | Investigate within 30 min |
| 2x | 3 days | Medium | Review in next business day |

---

## Prometheus Alert Rules

**File**: `observability/alerts/slo-alerts.yaml`

```yaml
groups:
  - name: slo_copilot_api
    interval: 30s
    rules:
      - alert: CopilotAPIHighErrorRate
        expr: |
          (sum(rate(http_requests_total{service="copilot-api", code=~"5.."}[5m])) 
          / sum(rate(http_requests_total{service="copilot-api"}[5m]))) > 0.01
        for: 5m
        labels:
          severity: warning
          service: copilot-api
        annotations:
          summary: "Copilot API error rate above budget"
          description: "Error rate is {{ $value | humanizePercentage }}, consuming error budget rapidly"
      
      - alert: CopilotAPIHighLatency
        expr: |
          histogram_quantile(0.95, 
            rate(http_request_duration_seconds_bucket{service="copilot-api"}[5m])
          ) > 2.0
        for: 10m
        labels:
          severity: warning
          service: copilot-api
        annotations:
          summary: "Copilot API p95 latency above SLO"
          description: "p95 latency is {{ $value }}s (SLO: 2s)"
```

---

## Grafana Dashboards

### SLO Overview Dashboard

**File**: `observability/dashboards/slo-overview.json`

**Panels**:
1. **Error Budget Burn Down** (time series)
   - Shows remaining error budget over 30-day window
   - Color-coded: green (>50%), yellow (20-50%), red (<20%)

2. **Service Availability** (gauge)
   - Current availability vs SLO target
   - Per service (Copilot API, RAG, Kafka, Airflow)

3. **Latency Heatmap** (heatmap)
   - Distribution of response times
   - Highlights p95/p99 thresholds

4. **Burn Rate Alert** (stat)
   - Current burn rate with alert threshold annotations

---

## SLO Review Cadence

| Frequency | Activity | Attendees |
|-----------|----------|-----------|
| **Weekly** | Review error budget status | Engineering team |
| **Monthly** | SLO achievement retrospective | Engineering + PM |
| **Quarterly** | SLO target adjustment (if needed) | Engineering + Leadership |

---

## Next Steps (Phase 6)

1. Implement Prometheus metrics for all SLIs
2. Create Grafana dashboards with error budget tracking
3. Deploy alert rules to Prometheus
4. Document runbooks for SLO breach scenarios
5. Establish on-call rotation and escalation policy

---

**Version**: 1.0  
**Last Updated**: 2026-02-04  
**Owner**: Platform Team
