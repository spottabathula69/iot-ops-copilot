# Production Airflow DAG Deployment Guide

## Overview

For production Airflow deployments, DAGs should be automatically synced from a Git repository rather than manually copied. This guide covers the recommended production approach using **Git-Sync**.

---

## GitSync Deployment (Recommended for Production)

Git-Sync is a sidecar container that continuously pulls DAGs from a Git repository and makes them available to Airflow.

### 1. Update Helm Values

Edit `infra/airflow/helm-values.yaml`:

```yaml
# DAGs configuration
dags:
  persistence:
    enabled: false
  
  gitSync:
    enabled: true
    repo: https://github.com/spottabathula69/iot-ops-copilot.git
    branch: main
    rev: HEAD
    depth: 1
    maxFailures: 0
    subPath: "apps/airflow/dags"  # Path to DAGs in repo
    wait: 60  # Sync interval in seconds
    
    # For private repositories, add SSH key or credentials:
    # sshKeySecret: airflow-git-ssh-secret
    # OR
    # credentialsSecret: airflow-git-credentials
```

### 2. Deploy with GitSync

```bash
# Upgrade Airflow with GitSync enabled
helm upgrade airflow apache-airflow/airflow \
  --namespace airflow \
  --values infra/airflow/helm-values.yaml \
  --version 1.13.1

# Wait for rollout
kubectl rollout status deployment/airflow-scheduler -n airflow
kubectl rollout status deployment/airflow-webserver -n airflow
```

### 3. Verify DAGs Are Synced

```bash
# Check Git-Sync sidecar logs
kubectl logs -n airflow deployment/airflow-scheduler -c git-sync

# List DAGs (should appear within 60 seconds)
kubectl exec -n airflow deployment/airflow-scheduler -- airflow dags list
```

### 4. For Private Repositories

Create SSH key secret:

```bash
# Generate SSH key (or use existing deploy key)
ssh-keygen -t ed25519 -C "airflow-gitsync" -f airflow-git-key -N ""

# Add public key to GitHub:
# Settings → Deploy keys → Add deploy key
# Paste contents of airflow-git-key.pub

# Create Kubernetes secret
kubectl create secret generic airflow-git-ssh-secret \
  --from-file=gitSshKey=airflow-git-key \
  -n airflow

# Update helm-values.yaml:
# dags.gitSync.sshKeySecret: airflow-git-ssh-secret
```

---

## Alternative: Persistent Volume DAGs

For environments where GitSync isn't suitable (e.g., air-gapped), use persistent volumes.

### 1. Create PersistentVolumeClaim

```yaml
# infra/airflow/dags-pvc.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: airflow-dags
  namespace: airflow
spec:
  accessModes:
    - ReadWriteMany  # Required for multiple pods
  resources:
    requests:
      storage: 1Gi
  storageClassName: standard  # Adjust for your cluster
```

```bash
kubectl apply -f infra/airflow/dags-pvc.yaml
```

### 2. Update Helm Values

```yaml
dags:
  persistence:
    enabled: true
    existingClaim: airflow-dags
    accessMode: ReadWriteMany
  
  gitSync:
    enabled: false
```

### 3. Copy DAGs to PVC

```bash
# Create a pod to copy files
kubectl run dag-uploader --rm -it --restart=Never \
  --image=busybox \
  --overrides='
{
  "spec": {
    "containers": [{
      "name": "dag-uploader",
      "image": "busybox",
      "command": ["sleep", "3600"],
      "volumeMounts": [{
        "name": "dags",
        "mountPath": "/dags"
      }]
    }],
    "volumes": [{
      "name": "dags",
      "persistentVolumeClaim": {
        "claimName": "airflow-dags"
      }
    }]
  }
}' \
  -n airflow

# In another terminal, copy DAGs
kubectl cp apps/airflow/dags/. airflow/dag-uploader:/dags/

# Kill the uploader pod
kubectl delete pod dag-uploader -n airflow
```

---

## Alternative: ConfigMap (Local Dev Only)

**⚠️ Not recommended for production** - ConfigMaps have 1MB size limit and require pod restarts.

### Create ConfigMap

```bash
kubectl create configmap airflow-dags \
  --from-file=apps/airflow/dags/ \
  -n airflow
```

### Update Helm Values

```yaml
extraVolumes:
  - name: dag-files
    configMap:
      name: airflow-dags

extraVolumeMounts:
  - name: dag-files
    mountPath: /opt/airflow/dags
```

**Limitations**:
- 1MB max size (restrictive for large DAGs)
- Requires deployment restart on updates
- Not suitable for production

---

## DAG Development Workflow

### 1. Local Development

```bash
# Create/edit DAG locally
vim apps/airflow/dags/my_new_dag.py

# Validate DAG syntax
python apps/airflow/dags/my_new_dag.py

# Test import
python -c "from airflow import DAG; import apps.airflow.dags.my_new_dag"
```

### 2. Commit and Push

```bash
git add apps/airflow/dags/my_new_dag.py
git commit -m "feat: Add my_new_dag for XYZ"
git push origin main
```

### 3. GitSync Auto-Deploy

- GitSync will pull changes within 60 seconds
- Scheduler will parse new DAG automatically
- DAG appears in Airflow UI (refresh to see)

### 4. Monitor Deployment

```bash
# Check Git-Sync pulled latest
kubectl logs -n airflow deployment/airflow-scheduler -c git-sync --tail=20

# Verify DAG exists
kubectl exec -n airflow deployment/airflow-scheduler -- airflow dags list | grep my_new_dag
```

---

## Troubleshooting

### DAG Not Appearing in UI

**1. Check Git-Sync**:
```bash
kubectl logs -n airflow deployment/airflow-scheduler -c git-sync
# Look for: "Synced successfully"
```

**2. Check DAG Parsing**:
```bash
kubectl logs -n airflow deployment/airflow-scheduler | grep "my_new_dag"
# Look for parsing errors
```

**3. Force Refresh**:
```bash
# Restart scheduler to force re-parse
kubectl rollout restart deployment/airflow-scheduler -n airflow
```

### Import Errors

```bash
# View DAG import errors in UI:
# Browse → DAG Runs → Select DAG → "i" icon → Import Errors

# Or via CLI:
kubectl exec -n airflow deployment/airflow-scheduler -- \
  airflow dags list-import-errors
```

### GitSync Authentication Failures

```bash
# Check secret exists
kubectl get secret airflow-git-ssh-secret -n airflow

# Verify SSH key format
kubectl get secret airflow-git-ssh-secret -n airflow -o jsonpath='{.data.gitSshKey}' | base64 -d | head -1
# Should show: "-----BEGIN OPENSSH PRIVATE KEY-----"
```

---

## Best Practices

### 1. DAG Testing

```python
# Always include DAG validation in CI/CD
# .github/workflows/test-dags.yml
name: Test DAGs
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Test DAG Syntax
        run: |
          pip install apache-airflow
          python -m py_compile apps/airflow/dags/*.py
```

### 2. DAG Versioning

- Use semantic versioning in DAG names: `etl_v2.py`
- Never delete DAGs that have historical runs
- Pause old DAGs instead: `airflow dags pause old_dag`

### 3. Secrets Management

```python
# Use Airflow Connections/Variables, not hardcoded secrets
from airflow.models import Variable

db_password = Variable.get("postgres_password", default_var="")
```

### 4. Resource Management

```yaml
# Set appropriate resources for KubernetesExecutor tasks
with DAG(...) as dag:
    task = KubernetesPodOperator(
        task_id="heavy_task",
        resources={
            "request_memory": "2Gi",
            "limit_memory": "4Gi",
            "request_cpu": "1000m",
            "limit_cpu": "2000m"
        }
    )
```

---

## Current Project Status

**For iot-ops-copilot project**:

- **Local Dev**: DAGs exist in `apps/airflow/dags/`
- **Kind Cluster**: ConfigMap approach didn't work due to volume mounting issues
- **Recommended Next Step**: Enable GitSync when deploying to production (AWS EKS, GCP GKE, etc.)

**To enable GitSync now** (for testing):
1. Push DAGs to your GitHub repo (already done)
2. Update `infra/airflow/helm-values.yaml` with GitSync config above
3. Run `helm upgrade airflow...`
4. DAGs will appear in UI within 60 seconds

---

## References

- [Airflow Helm Chart DAG Management](https://airflow.apache.org/docs/helm-chart/stable/manage-dags-files.html)
- [Git-Sync Documentation](https://github.com/kubernetes/git-sync)
- [Airflow Best Practices](https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html)
