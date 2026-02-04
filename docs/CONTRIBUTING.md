# Contributing to IoT Ops Copilot

Thank you for your interest in contributing! This document provides guidelines for development workflow, coding standards, and PR submission.

## Development Workflow

### 1. Setup Development Environment

```bash
# Clone repository
git clone <repo-url>
cd iot-ops-copilot

# Install dependencies
./scripts/dev-setup.sh

# Start local cluster
cd infra/terraform/bootstrap
terraform init && terraform apply

# Deploy platform
kubectl apply -f gitops/bootstrap/app-of-apps.yaml
```

### 2. Branch Strategy

- `main`: Production-ready code (protected)
- `develop`: Integration branch for next release
- `feature/*`: Feature branches (merge to develop)
- `fix/*`: Bug fixes (merge to develop or main for hotfixes)
- `docs/*`: Documentation updates

### 3. Commit Messages

Follow Conventional Commits:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `refactor`: Code restructuring
- `test`: Test additions/changes
- `chore`: Tooling, dependencies

**Examples**:
```
feat(copilot-api): add citation extraction to /ask endpoint

- Implement regex-based citation parsing from RAG context
- Add citation metadata to response payload
- Update OpenAPI schema

Closes #42
```

### 4. Pull Request Process

1. **Create PR** against `develop` (or `main` for hotfixes)
2. **Title**: Use conventional commit format
3. **Description**: Fill out PR template
4. **Review**: At least 1 approval required
5. **CI Checks**: All must pass (lint, test, build)
6. **Squash Merge**: Keep commit history clean

## Coding Standards

### Python (FastAPI, Airflow DAGs)

```python
# Use Black formatter (line length 100)
# Use isort for import organization
# Type hints required for all functions

from typing import List, Optional

def process_telemetry(
    device_id: str,
    metrics: List[dict],
    tenant_id: Optional[str] = None
) -> dict:
    """
    Process device telemetry and return enriched metrics.
    
    Args:
        device_id: Unique device identifier
        metrics: List of metric dictionaries
        tenant_id: Optional tenant for multi-tenant isolation
        
    Returns:
        Dictionary with processed metrics and metadata
    """
    # Implementation
    pass
```

**Linting**:
```bash
black apps/copilot-api/ --check
isort apps/copilot-api/ --check-only
mypy apps/copilot-api/
pylint apps/copilot-api/
```

### Go (Simulator)

```go
// Use gofmt and golangci-lint
// Follow Standard Go Project Layout

package simulator

// Device represents an IoT device with telemetry capabilities
type Device struct {
    ID       string
    TenantID string
    Model    string
}

// GenerateTelemetry produces sample telemetry data
func (d *Device) GenerateTelemetry() (*Telemetry, error) {
    // Implementation
    return nil, nil
}
```

**Linting**:
```bash
gofmt -s -w apps/simulator/
golangci-lint run apps/simulator/
```

### Terraform

```hcl
# Use terraform fmt
# Variables in variables.tf, outputs in outputs.tf

resource "kubernetes_namespace" "kafka" {
  metadata {
    name = "kafka"
    labels = {
      app     = "kafka"
      managed = "terraform"
    }
  }
}
```

**Validation**:
```bash
terraform fmt -check -recursive infra/terraform/
terraform validate
tflint
```

### YAML (Kubernetes, Argo CD)

```yaml
# Use yamllint
# 2-space indentation
# Alphabetize keys where logical

apiVersion: apps/v1
kind: Deployment
metadata:
  name: copilot-api
  namespace: copilot
  labels:
    app: copilot-api
    version: v1.0.0
spec:
  replicas: 3
  selector:
    matchLabels:
      app: copilot-api
```

**Linting**:
```bash
yamllint charts/ gitops/
```

## Testing Requirements

### Unit Tests

- **Python**: pytest with >80% coverage
  ```bash
  pytest apps/copilot-api/tests/ --cov=apps/copilot-api --cov-report=html
  ```

- **Go**: `go test` with table-driven tests
  ```bash
  go test ./apps/simulator/... -v -race -coverprofile=coverage.out
  ```

### Integration Tests

Located in `tests/integration/`:
```bash
# Start local cluster
kind create cluster --config infra/kind-config.yaml

# Run integration tests
pytest tests/integration/ -v
```

### Load Tests

Located in `loadtest/`:
```bash
k6 run --vus 100 --duration 30s loadtest/copilot-api.js
```

## Documentation

- **Code comments**: Public functions must have docstrings
- **ADRs**: Significant decisions require an ADR (use template in `docs/adr/000-template.md`)
- **Runbooks**: Operational procedures go in `docs/runbooks/`
- **README updates**: Keep main README in sync with implementation phases

## Pre-commit Hooks

Install pre-commit hooks:

```bash
pip install pre-commit
pre-commit install
```

Hooks run:
- Code formatters (black, gofmt, terraform fmt)
- Linters (pylint, golangci-lint)
- Secret scanning (detect-secrets)
- Trailing whitespace removal

## CI/CD Pipeline

GitHub Actions (`.github/workflows/`):

1. **Lint & Format** (on PR)
2. **Unit Tests** (on PR)
3. **Integration Tests** (on PR to main)
4. **Security Scan** (Trivy for container images)
5. **Build & Push Images** (on merge to main)
6. **Deploy to Dev** (auto, on merge to develop)
7. **Deploy to Prod** (manual approval required)

## Getting Help

- **Questions**: Open a GitHub Discussion
- **Bugs**: File an issue with `bug` label
- **Feature requests**: File an issue with `enhancement` label
- **Security issues**: Email security@example.com (do not file public issue)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
