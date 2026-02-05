# Apache Airflow Deployment on Kubernetes

This directory contains the configuration for deploying Apache Airflow using the official Helm chart.

## Architecture

- **Executor**: KubernetesExecutor (each task runs in its own pod)
- **Metadata DB**: PostgreSQL (deployed with Airflow)
- **Webserver**: 1 replica, accessible via port-forward
- **Scheduler**: 1 replica, scans DAGs every 30s
- **Triggerer**: 1 replica for deferrable operators

## Prerequisites

- Kubernetes cluster running (kind)
- Helm 3.x installed
- Postgres and MinIO already deployed (from Phase 1)

## Installation

### 1. Add Airflow Helm Repository

```bash
helm repo add apache-airflow https://airflow.apache.org
helm repo update
```

### 2. Create Namespace

```bash
kubectl apply -f namespace.yaml
```

### 3. Install Airflow

```bash
helm install airflow apache-airflow/airflow \
  --namespace airflow \
  --values helm-values.yaml \
  --version 1.13.1 \
  --timeout 10m
```

**Note**: Installation takes ~5-8 minutes. The chart will:
- Deploy PostgreSQL for metadata
- Run database migrations
- Create default admin user (admin/admin)
- Start webserver and scheduler

### 4. Wait for All Pods to be Ready

```bash
kubectl wait --for=condition=ready pod \
  -l component=webserver \
  -n airflow \
  --timeout=600s

kubectl wait --for=condition=ready pod \
  -l component=scheduler \
  -n airflow \
  --timeout=600s
```

### 5. Access Airflow UI

```bash
kubectl port-forward -n airflow svc/airflow-webserver 8080:8080
```

Then open: **http://localhost:8080**

**Credentials**: `admin` / `admin`

## Verification

### Check Pod Status

```bash
kubectl get pods -n airflow

# Expected output:
# NAME                                 READY   STATUS    RESTARTS   AGE
# airflow-postgresql-0                 1/1     Running   0          5m
# airflow-scheduler-xxx                2/2     Running   0          5m
# airflow-webserver-xxx                1/1     Running   0          5m
# airflow-triggerer-xxx                1/1     Running   0          5m
```

### Test Connections

```bash
# Enter scheduler pod
kubectl exec -it -n airflow deployment/airflow-scheduler -- bash

# Test Postgres connection
airflow connections test postgres_iot

# Test MinIO connection
airflow connections test minio

# List DAGs
airflow dags list
```

### Trigger a Test DAG

```bash
# Trigger example DAG (once custom DAGs are deployed)
kubectl exec -n airflow deployment/airflow-scheduler -- \
  airflow dags trigger bronze_to_silver_parquet

# Check DAG run status
kubectl exec -n airflow deployment/airflow-scheduler -- \
  airflow dags list-runs --dag-id bronze_to_silver_parquet
```

## Deployed DAGs

DAGs are located in `apps/airflow/dags/` and will be deployed via ConfigMap (Phase 2):

1. **bronze_to_silver_parquet** - Transform JSON from MinIO Bronze to Parquet in Silver
2. **silver_to_gold_aggregations** - Aggregate Silver data into Gold analytics tables
3. **telemetry_enrichment** - Enrich telemetry with metadata lookups

## Configuration

### Airflow Connections

Connections are pre-configured via environment variables:

- **postgres_iot**: PostgreSQL connection to `iot_ops` database
- **minio**: S3-compatible connection to MinIO

### Airflow Variables

Set via UI or CLI:
```bash
kubectl exec -n airflow deployment/airflow-scheduler -- \
  airflow variables set TELEMETRY_BATCH_SIZE 1000
```

## Monitoring

### Prometheus Metrics

Airflow exports StatsD metrics to Prometheus:
- `airflow_dag_duration`
- `airflow_dag_success_total`
- `airflow_dag_failure_total`
- `airflow_task_duration`
- `airflow_scheduler_heartbeat`

### Grafana Dashboard

Import dashboard from `observability/dashboards/airflow.json` (Phase 2).

## Troubleshooting

### Scheduler Not Starting

```bash
# Check logs
kubectl logs -n airflow deployment/airflow-scheduler

# Common issues:
# - Database migration failed → check PostgreSQL pod logs
# - Connection errors → verify postgres/minio services are running
```

### Webserver 503 Error

```bash
# Restart webserver
kubectl rollout restart deployment/airflow-webserver -n airflow
```

### Task Pods Stuck in Pending

```bash
# Check pod events
kubectl describe pod <task-pod-name> -n airflow

# Common causes:
# - Resource limits too high for kind cluster
# - Image pull errors
```

## Upgrading

```bash
helm upgrade airflow apache-airflow/airflow \
  --namespace airflow \
  --values helm-values.yaml \
  --version 1.13.1
```

## Uninstallation

```bash
helm uninstall airflow --namespace airflow
kubectl delete namespace airflow
```

## Next Steps

- [ ] Deploy DAGs via ConfigMap
- [ ] Create Bronze→Silver transformation DAG
- [ ] Create Silver→Gold aggregation DAG
- [ ] Set up Prometheus metrics scraping
- [ ] Create Grafana dashboard for DAG health

## References

- [Official Airflow Helm Chart](https://airflow.apache.org/docs/helm-chart/stable/index.html)
- [KubernetesExecutor Documentation](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/executor/kubernetes.html)
- [Airflow Connections](https://airflow.apache.org/docs/apache-airflow/stable/howto/connection.html)
