variable "cluster_name" {
  description = "Name of the kind cluster"
  type        = string
  default     = "iot-ops-local"
}

variable "k8s_version" {
  description = "Kubernetes version for the cluster"
  type        = string
  default     = "v1.30.0"
}

variable "worker_nodes" {
  description = "Number of worker nodes"
  type        = number
  default     = 2
}
