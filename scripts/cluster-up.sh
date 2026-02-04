#!/bin/bash
set -e

echo "🚀 Starting local Kubernetes cluster with Terraform..."

cd "$(dirname "$0")/../infra/terraform/bootstrap"

# Initialize Terraform if needed
if [ ! -d ".terraform" ]; then
    echo "Initializing Terraform..."
    terraform init
fi

# Apply Terraform configuration
echo "Creating kind cluster and deploying Argo CD..."
terraform apply -auto-approve

echo ""
echo "✅ Cluster is ready!"
echo ""

# Get cluster info
echo "Cluster information:"
kubectl cluster-info --context kind-iot-ops-local

echo ""
echo "Verify nodes:"
kubectl get nodes

echo ""
echo "Verify Argo CD pods:"
kubectl get pods -n argocd

echo ""
echo "=================================================="
echo "🎉 Bootstrap complete!"
echo ""
echo "Access services:"
echo "  Argo CD UI: Run './scripts/port-forward.sh' then open https://localhost:8080"
echo ""
echo "Get Argo CD admin password:"
echo "  kubectl get secret argocd-initial-admin-secret -n argocd -o jsonpath='{.data.password}' | base64 -d && echo"
echo ""
echo "Next: Apply app-of-apps manifest"
echo "  kubectl apply -f gitops/bootstrap/app-of-apps.yaml"
echo ""
