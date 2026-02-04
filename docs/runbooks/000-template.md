# Runbook Template

**Service**: [Service name]

**Severity**: [Critical | High | Medium | Low]

**Owner**: [Team or individual]

**Last Updated**: YYYY-MM-DD

---

## Symptoms

Describe the observable symptoms that indicate this issue:
- Alert: `<alert_name>` is firing
- User impact: [e.g., "Users see 500 errors on /ask endpoint"]
- Metrics: [e.g., "p95 latency > 5s"]

---

## Impact Assessment

| Severity | User Impact | SLO Burn Rate |
|----------|-------------|---------------|
| Critical | Complete outage | > 10x normal |
| High | Degraded performance | 3-10x normal |
| Medium | Intermittent errors | 1-3x normal |
| Low | No immediate impact | < 1x normal |

**Current Severity**: [Fill in based on above]

---

## Immediate Response (First 5 Minutes)

### 1. Verify the Issue

```bash
# Check pod status
kubectl get pods -n <namespace> -l app=<service>

# Check recent logs
kubectl logs -n <namespace> -l app=<service> --tail=100

# Check metrics
# Open Grafana dashboard: <link>
# Check panel: <panel_name>
```

### 2. Initial Triage

Quick checks to determine root cause area:

```bash
# Check resource usage
kubectl top pods -n <namespace>

# Check events
kubectl get events -n <namespace> --sort-by='.lastTimestamp' | tail -20

# Check dependencies
# [Service-specific health checks]
```

### 3. Communication

- Post in `#incidents` Slack channel
- Update status page if customer-facing impact
- Page on-call if Critical severity

---

## Investigation

### Possible Root Causes

1. **Cause 1**: [Description]
   - **Detection**: [How to verify this is the cause]
   - **Command**:
     ```bash
     # Diagnostic command
     ```

2. **Cause 2**: [Description]
   - **Detection**: [How to verify]
   - **Command**:
     ```bash
     # Diagnostic command
     ```

3. **Cause 3**: [Description]
   - **Detection**: [How to verify]
   - **Command**:
     ```bash
     # Diagnostic command
     ```

---

## Resolution Steps

### Solution for Cause 1

**Step-by-step**:

1. Action 1
   ```bash
   # Command with explanation
   kubectl <command>
   ```

2. Action 2
   ```bash
   # Command with explanation
   ```

3. Verify resolution
   ```bash
   # Verification command
   ```

**Expected outcome**: [What should happen after fix]

**Time to resolution**: ~X minutes

---

### Solution for Cause 2

[Repeat structure above]

---

## Prevention & Long-term Fixes

**Immediate preventions**:
- [ ] Action 1
- [ ] Action 2

**Long-term improvements** (file tickets):
- [ ] Improvement 1 (ticket: #XXX)
- [ ] Improvement 2 (ticket: #XXX)

---

## Rollback Procedure

If resolution attempts make things worse:

```bash
# Rollback command 1
kubectl rollout undo deployment/<name> -n <namespace>

# Rollback command 2
# [e.g., revert Argo CD to previous sync]
```

---

## Escalation

If issue persists after 30 minutes:

1. Escalate to: [Team lead / senior engineer]
2. Contact: [Slack handle / email / phone]
3. Bring in: [External team if dependency issue]

---

## Related Runbooks

- [Runbook: Related Issue 1](link)
- [Runbook: Related Issue 2](link)

---

## Post-Incident

After resolution:

1. [ ] Update this runbook with new learnings
2. [ ] Write post-mortem (use template in `docs/postmortems/template.md`)
3. [ ] Update alerts/dashboards if needed
4. [ ] File improvement tickets
