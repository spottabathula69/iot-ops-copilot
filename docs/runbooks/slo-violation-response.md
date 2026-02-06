# SLO Violation Response Runbook

## Purpose

This runbook provides step-by-step guidance for responding to Copilot API SLO violations and related alerts.

---

## Alert: `CopilotAPIDown`

**Severity**: Critical  
**Description**: API is not receiving requests or is completely down

### Immediate Actions

1. **Check pod status**
   ```bash
   kubectl get pods -l app=copilot-api
   kubectl describe pod <pod-name>
   ```

2. **Check recent logs**
   ```bash
   kubectl logs -l app=copilot-api --tail=100
   ```

3. **Check resource limits**
   ```bash
   kubectl top pods -l app=copilot-api
   ```

### Common Causes & Fixes

| Cause | Symptoms | Fix |
|-------|----------|-----|
| Pod crashed | CrashLoopBackOff status | Check logs for errors, fix code bug, redeploy |
| OOM killed | Last state: OOMKilled | Increase memory limits in deployment |
| Startup failure | Init:Error status | Check vLLM model loading, DB connection |
| Service misconfigured | Pod healthy but no traffic | Check Service selector labels |

### Escalation

If issue persists after 15 minutes, page on-call SRE.

---

## Alert: `CopilotHighErrorRate`

**Severity**: Critical  
**Description**: > 5% of requests returning 5xx errors

### Immediate Actions

1. **Identify error types**
   ```bash
   # Query Prometheus
   sum by (error_type) (rate(copilot_errors_total[5m]))
   ```

2. **Check recent deployments**
   ```bash
   kubectl rollout history deployment/copilot-api
   ```

3. **Review error logs**
   ```bash
   kubectl logs -l app=copilot-api | grep ERROR | tail -50
   ```

### Common Causes & Fixes

| Error Type | Likely Cause | Fix |
|------------|--------------|-----|
| Database connection errors | Postgres down or unreachable | Check DB pod, verify connection string |
| vLLM inference failures | Model not loaded, GPU OOM | Restart pod, check GPU memory |
| RAG search timeouts | Vector DB slow | Check pgvector performance, add indexes |
| Dependency errors | External service down | Check Kafka, MinIO, other deps |

### Mitigation

If errors spike after deployment, rollback:
```bash
kubectl rollout undo deployment/copilot-api
```

---

## Alert: `CopilotSLOViolationLatency`

**Severity**: Critical  
**Description**: p95 latency > 1 second for 10+ minutes

### Immediate Actions

1. **Check latency breakdown (Jaeger)**
   - Open Jaeger UI: `kubectl port-forward -n monitoring svc/jaeger 16686:16686`
   - Navigate to http://localhost:16686
   - Search for slow traces (duration > 1s)
   - Identify bottleneck component

2. **Check resource utilization**
   ```bash
   kubectl top pods -l app=copilot-api
   ```

3. **Check GPU utilization**
   ```promql
   copilot_gpu_utilization_percent
   ```

### Latency Breakdown Analysis

Use Jaeger to identify which component is slow:

**If RAG search is slow (> 200ms)**:
- Check pgvector query performance
- Verify hybrid search isn't scanning too many rows
- Consider adding database indexes
- Reduce `top_k` parameter

**If LLM inference is slow (> 500ms)**:
- Check GPU utilization (should be 80-90%)
- If GPU at 100%: Scale replicas or throttle requests
- If GPU low: Check vLLM configuration, model loaded
- Consider using smaller model (TinyLlama vs Llama2)

**If reranking is slow (> 100ms)**:
- Check reranker model loaded
- Reduce number of candidates to rerank
- Consider caching reranking results

### Mitigation

**Short-term:**
- Increase cache TTL to reduce cache misses
- Scale horizontally (add replicas)
- Reduce `max_context` chunks

**Long-term:**
- Optimize RAG queries with better indexes
- Use quantized LLM model for faster inference
- Implement request prioritization/throttling

---

## Alert: `CopilotLowQuality`

**Severity**: Critical  
**Description**: RAG precision < 85% for 15+ minutes

### Immediate Actions

1. **Check recent queries**
   ```bash
   kubectl logs -l app=copilot-api | grep "RAG precision" | tail -20
   ```

2. **Check reranker status**
   ```promql
   copilot_rag_precision
   ```

3. **Sample query quality**
   - Run test queries via `/ask` endpoint
   - Manually verify citation relevance

### Common Causes & Fixes

| Cause | Symptoms | Fix |
|-------|----------|-----|
| Reranker not loaded | Precision drops to 0.6-0.7 | Check reranker pod, restart if needed |
| Poor embedding quality | Low semantic search scores | Verify embedder model version |
| Stale documentation | Old manuals indexed | Re-ingest latest docs |
| Query mismatch | User queries very different from docs | Update documentation coverage |

### Mitigation

1. Enable reranking if disabled
2. Adjust hybrid search weights (BM25 vs vector)
3. Update document chunking strategy
4. Review and update knowledge base

---

## Alert: `CopilotErrorBudgetExhausted`

**Severity**: Critical  
**Description**: 30-day error budget fully consumed

### Impact

Any further violations will breach the SLO and affect monthly SLA.

### Immediate Actions

1. **Stop all non-critical changes**
   - Freeze deployments
   - Defer feature releases

2. **Focus on stability**
   - Monitor all metrics closely
   - Fix any active issues immediately
   - Increase monitoring frequency

3. **Communicate with stakeholders**
   - Notify product team of SLO status
   - Set expectations for reduced velocity

### Recovery

Error budget resets gradually over the 30-day window. To recover:

1. **Maintain 100% uptime** for next 7-10 days
2. **Keep p95 latency < 800ms** (well below SLO)
3. **Zero 5xx errors** if possible

Monitor error budget daily:
```promql
copilot:availability:error_budget_consumed
copilot:latency:error_budget_consumed
```

---

## General Debugging Tools

### Check metrics
```bash
# Port-forward Prometheus
kubectl port-forward -n monitoring svc/prometheus 9090:9090

# Navigate to http://localhost:9090
```

### Check traces
```bash
# Port-forward Jaeger
kubectl port-forward -n monitoring svc/jaeger 16686:16686

# Navigate to http://localhost:16686
```

### Check dashboards
```bash
# Port-forward Grafana
kubectl port-forward -n monitoring svc/grafana 3000:80

# Navigate to http://localhost:3000
```

### Check logs
```bash
# Tail logs
kubectl logs -f -l app=copilot-api

# Search for errors
kubectl logs -l app=copilot-api | grep -i error | tail -50

# Export logs for analysis
kubectl logs -l app=copilot-api --since=1h > copilot-logs.txt
```

---

## Contact

- On-call SRE: PagerDuty
- Product Owner: [contact info]
- Engineering Lead: [contact info]

---

## References

- [Copilot API Architecture](/docs/ARCHITECTURE.md)
- [Deployment Guide](/infra/README.md)
- [Prometheus Queries](http://localhost:9090)
- [Grafana Dashboards](http://localhost:3000)
- [Jaeger Traces](http://localhost:16686)
