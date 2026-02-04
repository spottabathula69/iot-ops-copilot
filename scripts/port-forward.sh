#!/bin/bash

echo "🔌 Setting up port forwarding for local access..."

# Function to port forward in background
port_forward() {
    local service=$1
    local namespace=$2
    local local_port=$3
    local remote_port=$4
    local name=$5
    
    echo "Forwarding $name: localhost:$local_port -> $service:$remote_port"
    kubectl port-forward -n $namespace svc/$service $local_port:$remote_port > /dev/null 2>&1 &
}

# Kill existing port-forward processes
pkill -f "kubectl port-forward" || true

# Wait a moment
sleep 2

# Argo CD
port_forward "argocd-server" "argocd" "8080" "443" "Argo CD"

# Future: Grafana (Phase 6)
# port_forward "grafana" "observability" "3000" "80" "Grafana"

# Future: Copilot UI (Phase 5)
# port_forward "copilot-ui" "copilot" "8501" "8501" "Copilot UI"

sleep 2

echo ""
echo "✅ Port forwarding active!"
echo ""
echo "Access services:"
echo "  Argo CD:  https://localhost:8080 (username: admin)"
echo ""
echo "Get Argo CD password:"
echo "  kubectl get secret argocd-initial-admin-secret -n argocd -o jsonpath='{.data.password}' | base64 -d && echo"
echo ""
echo "To stop port forwarding:"
echo "  pkill -f 'kubectl port-forward'"
echo ""
echo "Press Ctrl+C to stop all port forwards and exit."

# Wait indefinitely
wait
