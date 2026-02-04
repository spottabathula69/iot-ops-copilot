#!/bin/bash
set -e

echo "🚀 IoT Ops Copilot - Development Environment Setup"
echo "=================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to print status
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✔${NC} $2"
    else
        echo -e "${RED}✘${NC} $2"
    fi
}

echo ""
echo "Checking required dependencies..."
echo ""

# Check Docker
if command_exists docker; then
    DOCKER_VERSION=$(docker --version | cut -d ' ' -f3 | cut -d ',' -f1)
    print_status 0 "Docker ($DOCKER_VERSION)"
else
    print_status 1 "Docker not found. Please install: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check kubectl
if command_exists kubectl; then
    KUBECTL_VERSION=$(kubectl version --client -o json 2>/dev/null | grep -o '"gitVersion":"[^"]*' | cut -d'"' -f4)
    print_status 0 "kubectl ($KUBECTL_VERSION)"
else
    print_status 1 "kubectl not found. Installing..."
    # Install kubectl (Linux)
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
    chmod +x kubectl
    sudo mv kubectl /usr/local/bin/
    print_status 0 "kubectl installed"
fi

# Check kind
if command_exists kind; then
    KIND_VERSION=$(kind version | cut -d ' ' -f2)
    print_status 0 "kind ($KIND_VERSION)"
else
    print_status 1 "kind not found. Installing..."
    curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64
    chmod +x ./kind
    sudo mv ./kind /usr/local/bin/kind
    print_status 0 "kind installed"
fi

# Check Helm
if command_exists helm; then
    HELM_VERSION=$(helm version --short | cut -d ' ' -f1 | cut -d'+' -f1)
    print_status 0 "Helm ($HELM_VERSION)"
else
    print_status 1 "Helm not found. Installing..."
    curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
    print_status 0 "Helm installed"
fi

# Check Terraform
if command_exists terraform; then
    TERRAFORM_VERSION=$(terraform version -json | grep -o '"terraform_version":"[^"]*' | cut -d'"' -f4)
    print_status 0 "Terraform ($TERRAFORM_VERSION)"
else
    print_status 1 "Terraform not found. Please install: https://developer.hashicorp.com/terraform/install"
    exit 1
fi

# Optional: Check k9s (nice-to-have for cluster management)
if command_exists k9s; then
    K9S_VERSION=$(k9s version --short 2>/dev/null || echo "unknown")
    print_status 0 "k9s ($K9S_VERSION) - Optional but recommended"
else
    echo -e "${YELLOW}ℹ${NC} k9s not found (optional). Install for better cluster management: https://k9scli.io/"
fi

echo ""
echo "=================================================="
echo -e "${GREEN}✔ All required dependencies are installed!${NC}"
echo ""
echo "Next steps:"
echo "  1. cd infra/terraform/bootstrap"
echo "  2. terraform init"
echo "  3. terraform apply"
echo "  4. Access Argo CD: kubectl port-forward svc/argocd-server -n argocd 8080:443"
echo ""
echo "Or use the quick start script:"
echo "  ./scripts/cluster-up.sh"
echo ""
