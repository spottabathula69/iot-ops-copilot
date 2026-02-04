output "cluster_name" {
  description = "The name of the kind cluster"
  value       = kind_cluster.iot_ops.name
}

output "kubeconfig_path" {
  description = "Path to the kubeconfig file"
  value       = kind_cluster.iot_ops.kubeconfig_path
}

output "api_server_endpoint" {
  description = "Kubernetes API server endpoint"
  value       = kind_cluster.iot_ops.endpoint
}

output "argocd_admin_password" {
  description = "Argo CD admin password (initial)"
  value       = "Run: kubectl get secret argocd-initial-admin-secret -n argocd -o jsonpath='{.data.password}' | base64 -d"
  sensitive   = false
}
