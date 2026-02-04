terraform {
  required_version = ">= 1.5"
  
  required_providers {
    kind = {
      source  = "tehcyx/kind"
      version = "~> 0.2"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.11"
    }
  }
}

provider "kind" {}

provider "kubernetes" {
  config_path = pathexpand("~/.kube/config")
  config_context = "kind-${var.cluster_name}"
}

provider "helm" {
  kubernetes {
    config_path = pathexpand("~/.kube/config")
    config_context = "kind-${var.cluster_name}"
  }
}
