# kind Cluster Quick Start

This guide helps you create and manage the local kind (Kubernetes IN Docker) cluster.

## Prerequisites

- Docker running
- kind installed (`kind version` to check)
- kubectl installed

## Create Cluster

```bash
# Create 4-node cluster (1 control-plane + 3 workers)
kind create cluster --config infra/kind-config.yaml

# This creates a cluster named: iot-ops-copilot
```

## Verify Cluster

```bash
# Check cluster exists
kind get clusters

# Should output: iot-ops-copilot

# Check nodes
kubectl get nodes

# Expected output:
# NAME                            STATUS   ROLES           AGE
# iot-ops-copilot-control-plane   Ready    control-plane   2m
# iot-ops-copilot-worker          Ready    <none>          2m
# iot-ops-copilot-worker2         Ready    <none>          2m
# iot-ops-copilot-worker3         Ready    <none>          2m
```

## kubectl Context

kind automatically sets your kubectl context:

```bash
# Show current context
kubectl config current-context

# Should output: kind-iot-ops-copilot

# If not, switch to it:
kubectl config use-context kind-iot-ops-copilot
```

## Delete Cluster

```bash
# Delete cluster and all resources
kind delete cluster --name iot-ops-copilot
```

## Load Local Images (for simulator)

```bash
# Build simulator image
docker build -t iot-simulator:latest apps/simulator/

# Load into kind cluster
kind load docker-image iot-simulator:latest --name iot-ops-copilot

# Now K8s can use imagePullPolicy: IfNotPresent
```

## Cluster Info

```bash
# Get cluster info
kubectl cluster-info --context kind-iot-ops-copilot

# Check all resources
kubectl get all --all-namespaces
```

## Troubleshooting

### Cluster won't create
```bash
# Check Docker is running
docker ps

# Delete existing cluster if name conflicts
kind delete cluster --name iot-ops-copilot

# Try again
kind create cluster --config infra/kind-config.yaml
```

### kubectl can't connect
```bash
# Verify context
kubectl config get-contexts

# Switch to kind context
kubectl config use-context kind-iot-ops-copilot
```

### Out of resources
```bash
# Check Docker resources (Settings → Resources)
# Recommended: 4 CPUs, 8GB RAM for this cluster

# Or reduce worker nodes in kind-config.yaml to 2 workers
```

## Next Steps

Once cluster is ready, deploy Kafka:
```bash
# See: infra/kafka/README.md
helm install strimzi-kafka-operator strimzi/strimzi-kafka-operator \
  --namespace kafka \
  --create-namespace \
  --values infra/kafka/strimzi-operator.yaml
```
