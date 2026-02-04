# ADR-001: Local Kubernetes Distribution

**Status**: Accepted

**Date**: 2026-02-04

**Deciders**: Platform Team

**Technical Story**: Need to choose local Kubernetes environment for development and testing that closely mirrors production (EKS/GKE).

## Context and Problem Statement

Developers need a local Kubernetes environment to:
- Test full stack locally before committing
- Run integration tests in CI/CD
- Debug platform issues without cloud costs
- Ensure parity with production EKS/GKE environments

Key requirements:
- Support for LoadBalancer and Ingress
- Multi-node capability for testing scheduling/affinity
- Persistent volume support
- Minimal resource overhead
- Easy CI/CD integration

## Decision Drivers

- **Developer Experience**: Fast startup, easy reset, familiar tooling
- **CI/CD Compatibility**: Runs in GitHub Actions or GitLab CI
- **Production Parity**: Behaves like EKS/GKE (networking, storage classes)
- **Resource Efficiency**: Runs on laptops with 16GB RAM
- **Community Support**: Active maintenance, good documentation

## Considered Options

- Option 1: **kind** (Kubernetes in Docker)
- Option 2: **minikube**
- Option 3: **k3d** (k3s in Docker)

## Decision Outcome

**Chosen option**: "kind", because it offers the best balance of production parity, CI/CD integration, and multi-node support.

### Consequences

**Good**:
- Excellent CI/CD integration (runs in Docker, no VM needed)
- Multi-node clusters trivial to create via config file
- Widely used in Kubernetes community (CNCF projects use it for testing)
- LoadBalancer support via MetalLB or cloud-provider-kind
- Fast cluster creation (~30 seconds)

**Bad**:
- No built-in GUI (must use kubectl + k9s/lens separately)
- LoadBalancer requires additional setup (MetalLB)
- Less feature-rich than minikube (no addons system)

**Neutral**:
- Requires Docker (not Podman) for best compatibility
- Image loading requires explicit `kind load docker-image` commands

### Confirmation

Success criteria:
- Developers can bring up full stack in <5 minutes
- CI pipeline can run integration tests against kind cluster
- Multi-node test scenarios (pod affinity, node taints) work correctly

## Pros and Cons of the Options

### Option 1: kind

**Description**: kind (Kubernetes IN Docker) runs K8s nodes as Docker containers. Originally built for testing Kubernetes itself, now widely used for local dev.

**Pros**:
- Native Docker integration (no VM overhead)
- Excellent for CI/CD (GitHub Actions, GitLab CI)
- Multi-node clusters via simple YAML config
- Production-like networking (no special tunnels)
- Supports Kubernetes versions 1.25-1.30

**Cons**:
- No addon ecosystem (must manually install MetalLB, Ingress)
- No built-in dashboard
- Requires explicit image loading (via `kind load docker-image`)

### Option 2: minikube

**Description**: Mature local K8s solution with VM or Docker driver. Rich addon system (dashboard, metrics-server, ingress).

**Pros**:
- Mature and widely documented
- Rich addon ecosystem (`minikube addons enable ingress`)
- Built-in tunneling for LoadBalancer services
- GUI dashboard out-of-box
- Supports multiple drivers (Docker, VirtualBox, Hyperkit)

**Cons**:
- Slower startup than kind (~60-90 seconds)
- Multi-node support experimental (requires profile per node)
- CI/CD integration more complex (requires VM or Docker-in-Docker)
- Higher resource usage with VM driver

### Option 3: k3d

**Description**: Lightweight K8s distribution (k3s) running in Docker containers. Optimized for edge/IoT but works great for local dev.

**Pros**:
- Very fast startup (~20 seconds)
- Built-in LoadBalancer (Traefik Ingress included)
- Multi-node trivial via CLI flags
- Smallest resource footprint

**Cons**:
- Uses k3s (not vanilla K8s) - some differences from EKS/GKE
- Smaller community than kind or minikube
- Traefik as default Ingress (not nginx) - different configs
- Less production-representative due to k3s optimizations

## More Information

- kind documentation: https://kind.sigs.k8s.io/
- Production migration path: Terraform modules will abstract K8s API, allowing seamless move from kind → EKS/GKE
- Related: ADR-002 will cover GitOps tooling choice (Argo CD vs Flux)
