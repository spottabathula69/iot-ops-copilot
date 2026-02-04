# ADR-002: GitOps Tooling (Argo CD vs Flux)

**Status**: Accepted

**Date**: 2026-02-04

**Deciders**: Platform Team

**Technical Story**: Select GitOps tool for declarative deployment of infrastructure and applications.

## Context and Problem Statement

We need a GitOps solution that:
- Manages both infrastructure components (Kafka, Airflow, Prometheus) and applications
- Supports multi-environment deployments (local, dev, prod)
- Provides visibility into deployment status and health
- Integrates with Kubernetes RBAC
- Enables progressive delivery (future requirement)

## Decision Drivers

- **Ease of Use**: Developer-friendly UI and CLI
- **Multi-tenancy**: Support for isolating tenant deployments
- **App-of-Apps**: Hierarchical application management
- **Community**: Mature project with active development
- **Extensibility**: Plugin support for custom health checks

## Considered Options

- Option 1: **Argo CD**
- Option 2: **Flux CD**

## Decision Outcome

**Chosen option**: "Argo CD", because app-of-apps pattern, UI, and multi-tenancy features align better with our needs.

### Consequences

**Good**:
- Excellent UI for visualizing app hierarchy and sync status
- App-of-apps pattern perfect for our infra + apps structure
- Mature RBAC and multi-tenancy support
- Integrates with Argo Rollouts for future progressive delivery
- Large community and extensive documentation

**Bad**:
- Heavier resource footprint than Flux (Redis, Dex for SSO)
- UI can become cluttered with hundreds of apps (pagination helps)
- Requires separate tool (Argo Rollouts) for canary deployments

**Neutral**:
- Pull-based model (both Argo and Flux use this)
- Requires Git repo structure discipline

### Confirmation

Success criteria:
- Single `kubectl apply` bootstraps entire platform (app-of-apps)
- Developers can see deployment status without `kubectl`
- Rollback to previous version takes <2 minutes

## Pros and Cons of the Options

### Option 1: Argo CD

**Description**: Declarative GitOps CD for Kubernetes with web UI. CNCF graduated project.

**Pros**:
- Rich web UI (application tree, diff view, sync waves)
- App-of-apps and ApplicationSets for dynamic app generation
- Strong RBAC (project-based isolation)
- Supports Helm, Kustomize, raw YAML
- Extensive webhook and notification support
- Active community (CNCF graduated)

**Cons**:
- Requires Redis and optionally Dex (more components)
- UI can be overwhelming for large deployments
- Sync can be slow with very large repos

### Option 2: Flux CD

**Description**: GitOps toolkit for Kubernetes. Lightweight, CLI-first, CNCF incubating.

**Pros**:
- Very lightweight (no database, minimal resources)
- Better OCI support (Helm charts from OCI registries)
- Flux CLI excellent for troubleshooting
- Integrated with Flagger for progressive delivery
- Strong multi-tenancy via namespaces

**Cons**:
- No built-in UI (must use weave-gitops or external tools)
- App-of-apps pattern less intuitive (Kustomizations reference other Kustomizations)
- Smaller community than Argo CD
- RBAC setup more manual

## More Information

- Argo CD: https://argo-cd.readthedocs.io/
- App-of-apps example: `gitops/bootstrap/app-of-apps.yaml` will define root app
- Future: May evaluate Argo Rollouts for blue/green and canary in Phase 7
