# Runbook: Stuck DAG Investigation

**Alert**: `DAGStuck` - Airflow DAG hasn't completed successfully in over 2 hours

**Severity**: Critical

**On-Call Team**: Data Engineering

---

## Symptoms

- DAG shows "running" status for > 1 hour
- No task progress visible in Airflow UI
- Alert triggered: `DAGStuck` or `DAGFailed`
- Data freshness metrics show stale data

---

## Initial Triage

### 1. Check DAG Status in Airflow UI

```bash
# Port-forward to Airflow webserver
kubectl port-forward -n airflow svc/airflow-webserver 8080:8080

# Open http://localhost:8080
# Navigate to: DAGs → [stuck DAG name] → Graph View
```

**Look for**:
- Tasks stuck in "running" or "queued" state
- Failed tasks (red boxes)
- Upstream failures blocking downstream tasks

### 2. Check Airflow Scheduler Health

```bash
# View scheduler logs
kubectl logs -n airflow deployment/airflow-scheduler --tail=100 | grep ERROR

# Check scheduler heartbeat
kubectl exec -n airflow deployment/airflow-scheduler -- \
  airflow jobs check --job-type SchedulerJob --hostname $(hostname)
```

**Common issues**:
- `OperationalError: could not connect to server` → Database connection lost
- `ConnectionResetError` → Network issues
- `Scheduler appears to have stopped` → Scheduler crashed

---

## Investigation Steps

### Step 1: Identify Stuck Task

```bash
# List running DAG runs
kubectl exec -n airflow deployment/airflow-scheduler -- \
  airflow dags list-runs --state running

# Get task instances for specific DAG
kubectl exec -n airflow deployment/airflow-scheduler -- \
  airflow tasks list <dag_id> --tree
```

### Step 2: Check Task Logs

**Via UI**:
1. Open Airflow UI → DAGs → [DAG name]
2. Click on stuck task (colored box)
3. Click "Log" button
4. Look for Python exceptions, connection errors

**Via CLI**:
```bash
# View task logs
kubectl exec -n airflow deployment/airflow-scheduler -- \
  airflow tasks logs <dag_id> <task_id> <execution_date>
```

**Common errors**:
- `Connection refused` → Service (Postgres/MinIO) down
- `Timeout` → Query taking too long
- `Out of memory` → Pod killed by OOMKiller
- `ModuleNotFoundError` → Missing Python dependency

### Step 3: Check Task Pod Status (KubernetesExecutor)

```bash
# List all Airflow task pods
kubectl get pods -n airflow | grep <dag_id>

# Describe stuck pod
kubectl describe pod -n airflow <pod-name>

# Check pod logs
kubectl logs -n airflow <pod-name>
```

**Common pod issues**:
- `Pending` → Insufficient resources, check `kubectl describe pod`
- `CrashLoopBackOff` → Task failing repeatedly
- `ImagePullBackOff` → Docker image not found
- `OOMKilled` → Memory limit too low

### Step 4: Check Database Connections

```bash
# Test Postgres connection
kubectl exec -n airflow deployment/airflow-scheduler -- \
  airflow connections test postgres_iot

# Test MinIO connection
kubectl exec -n airflow deployment/airflow-scheduler -- \
  airflow connections test minio
```

### Step 5: Check External Dependencies

**Postgres**:
```bash
kubectl get pods -n postgres
kubectl logs -n postgres postgres-0 --tail=50
```

**MinIO**:
```bash
kubectl get pods -n minio
kubectl exec -n minio deployment/minio -- mc admin info local
```

**Kafka** (if DAG consumes from Kafka):
```bash
kubectl get pods -n kafka | grep broker
```

---

## Common Root Causes & Resolutions

### 1. Task Timeout

**Symptoms**: Task runs for hours, no progress

**Resolution**:
```bash
# Mark task as failed to unblock
kubectl exec -n airflow deployment/airflow-scheduler -- \
  airflow tasks clear <dag_id> <task_id> <execution_date> --yes

# OR set execution_timeout in DAG
# In DAG file:
# task = PythonOperator(..., execution_timeout=timedelta(minutes=30))
```

### 2. Database Connection Pool Exhausted

**Symptoms**: `OperationalError: too many connections`

**Resolution**:
```bash
# Restart Airflow scheduler
kubectl rollout restart deployment/airflow-scheduler -n airflow

# Scale down concurrent DAG runs (update helm-values.yaml):
# config.core.max_active_tasks_per_dag: 8  # Reduce from 16
```

### 3. Out of Memory (OOMKilled)

**Symptoms**: Pod status shows `OOMKilled`, task logs cut off abruptly

**Resolution**:
```bash
# Increase memory limits in helm-values.yaml:
# workers.resources.limits.memory: "2Gi"  # Increase from 1Gi

# Upgrade Helm release
helm upgrade airflow apache-airflow/airflow \
  --namespace airflow \
  --values infra/airflow/helm-values.yaml
```

### 4. Scheduler Dead/Frozen

**Symptoms**: No DAGs running, scheduler pod in `CrashLoopBackOff`

**Resolution**:
```bash
# Check scheduler logs
kubectl logs -n airflow deployment/airflow-scheduler --previous

# Restart scheduler
kubectl rollout restart deployment/airflow-scheduler -n airflow

# If persistent, check metadata DB health:
kubectl exec -n airflow airflow-postgresql-0 -- \
  psql -U postgres -d airflow -c "SELECT pid, state, query FROM pg_stat_activity WHERE state != 'idle';"
```

### 5. DAG Import Errors

**Symptoms**: DAG not visible in UI, scheduler logs show `Failed to import`

**Resolution**:
```bash
# Check DAG parsing logs
kubectl logs -n airflow deployment/airflow-scheduler | grep "Failed to import"

# Validate DAG syntax locally
python apps/airflow/dags/<dag_file>.py

# Fix syntax error, redeploy DAG
# (DAGs will auto-refresh after dag_dir_list_interval seconds)
```

---

## Manual Intervention

### Clear Stuck DAG Run

```bash
# Mark entire DAG run as failed
kubectl exec -n airflow deployment/airflow-scheduler -- \
  airflow dags delete <dag_id> --yes

# Trigger new run
kubectl exec -n airflow deployment/airflow-scheduler -- \
  airflow dags trigger <dag_id>
```

### Pause DAG to Stop Processing

```bash
kubectl exec -n airflow deployment/airflow-scheduler -- \
  airflow dags pause <dag_id>
```

### Force Task Success (Use Sparingly!)

```bash
kubectl exec -n airflow deployment/airflow-scheduler -- \
  airflow tasks state-set <dag_id> <task_id> <execution_date> success
```

---

## Prevention

### Best Practices

1. **Set timeouts**:
   ```python
   dag = DAG(..., dagrun_timeout=timedelta(hours=2))
   task = PythonOperator(..., execution_timeout=timedelta(minutes=30))
   ```

2. **Add retries**:
   ```python
   default_args = {'retries': 3, 'retry_delay': timedelta(minutes=5)}
   ```

3. **Monitor metrics**:
   - `airflow_dag_duration_seconds` - Track p95/p99
   - `airflow_scheduler_heartbeat` - Scheduler liveness
   - `airflow_task_duration_seconds` - Task performance

4. **Resource limits**:
   - Set appropriate CPU/memory for task pods
   - Monitor `kubectl top pods -n airflow`

5. **Alerting**:
   - Alert on `DAGStuck` (no success in 2h)
   - Alert on `DAGFailed` (increase in failures)
   - Alert on scheduler heartbeat miss

---

## Escalation

If issue persists after 30 minutes:
1. **Notify**: Data Engineering Lead
2. **Communicate**: Post in #data-incidents Slack channel
3. **Document**: Update incident log with findings
4. **Mitigate**: Pause affected DAGs to prevent cascading failures

---

## Post-Incident

1. Update DAG with fixes (timeouts, error handling)
2. Add monitoring if root cause wasn't detected
3. Document in post-mortem
4. Update this runbook with new learnings
