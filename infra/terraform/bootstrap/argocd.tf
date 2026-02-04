resource "helm_release" "argocd" {
  depends_on = [kubernetes_namespace.argocd]
  
  name       = "argocd"
  repository = "https://argoproj.github.io/argo-helm"
  chart      = "argo-cd"
  version    = "5.51.6"  # Latest stable as of Feb 2024
  namespace  = "argocd"
  
  values = [
    yamlencode({
      global = {
        domain = "argocd.local"
      }
      
      server = {
        service = {
          type = "ClusterIP"
        }
        
        extraArgs = [
          "--insecure"  # Disable TLS for local development
        ]
      }
      
      # Enable notifications for future use
      notifications = {
        enabled = true
      }
      
      # ApplicationSet controller for dynamic app generation
      applicationSet = {
        enabled = true
      }
    })
  ]
  
  timeout = 600
  wait    = true
}

# Wait for Argo CD to be ready before proceeding
resource "null_resource" "wait_for_argocd" {
  depends_on = [helm_release.argocd]
  
  provisioner "local-exec" {
    command = <<-EOT
      echo "Waiting for Argo CD server to be ready..."
      kubectl wait --for=condition=available --timeout=300s \
        deployment/argocd-server -n argocd
    EOT
  }
}
