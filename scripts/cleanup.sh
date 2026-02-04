#!/bin/bash

echo "🧹 Cleaning up local environment..."

# Change to terraform directory
cd "$(dirname "$0")/../infra/terraform/bootstrap"

# Destroy Terraform resources
echo "Destroying Terraform resources..."
terraform destroy -auto-approve || true

# Force delete kind cluster if Terraform fails
echo "Ensuring kind cluster is deleted..."
kind delete cluster --name iot-ops-local || true

# Kill any port-forward processes
echo "Stopping port-forward processes..."
pkill -f "kubectl port-forward" || true

echo ""
echo "✅ Cleanup complete!"
echo ""
echo "To recreate the cluster, run:"
echo "  ./scripts/cluster-up.sh"
echo ""
