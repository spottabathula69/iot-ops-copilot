resource "kind_cluster" "iot_ops" {
  name           = var.cluster_name
  wait_for_ready = true
  
  kind_config {
    kind        = "Cluster"
    api_version = "kind.x-k8s.io/v1alpha4"
    
    node {
      role = "control-plane"
      
      # Enable Ingress by exposing ports 80 and 443
      extra_port_mappings {
        container_port = 80
        host_port      = 80
        protocol       = "TCP"
      }
      
      extra_port_mappings {
        container_port = 443
        host_port      = 443
        protocol       = "TCP"
      }
    }
    
    # Worker nodes for realistic scheduling scenarios
    dynamic "node" {
      for_each = range(var.worker_nodes)
      content {
        role = "worker"
      }
    }
  }
}

# Create namespaces for core services
resource "kubernetes_namespace" "argocd" {
  depends_on = [kind_cluster.iot_ops]
  
  metadata {
    name = "argocd"
    labels = {
      name    = "argocd"
      managed = "terraform"
    }
  }
}

resource "kubernetes_namespace" "kafka" {
  depends_on = [kind_cluster.iot_ops]
  
  metadata {
    name = "kafka"
    labels = {
      name    = "kafka"
      managed = "terraform"
    }
  }
}

resource "kubernetes_namespace" "airflow" {
  depends_on = [kind_cluster.iot_ops]
  
  metadata {
    name = "airflow"
    labels = {
      name    = "airflow"
      managed = "terraform"
    }
  }
}

resource "kubernetes_namespace" "copilot" {
  depends_on = [kind_cluster.iot_ops]
  
  metadata {
    name = "copilot"
    labels = {
      name    = "copilot"
      managed = "terraform"
    }
  }
}

resource "kubernetes_namespace" "observability" {
  depends_on = [kind_cluster.iot_ops]
  
  metadata {
    name = "observability"
    labels = {
      name    = "observability"
      managed = "terraform"
    }
  }
}
