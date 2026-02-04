variable "region" {
  type    = string
  default = "us-east-1"
}

variable "environment" {
  type    = string
  default = "prod"
}

variable "name" {
  type    = string
  default = "supportlens"
}

variable "certificate_arn" {
  description = "ACM certificate for the HTTPS listener (in the same region)."
  type        = string
}

variable "image_tag" {
  description = "Tag of the api and web images in ECR (the git SHA; repositories are immutable)."
  type        = string
}

variable "llm_provider" {
  description = "anthropic or fake. With anthropic, put the key in the anthropic_api_key secret."
  type        = string
  default     = "anthropic"
}

variable "llm_model" {
  type    = string
  default = "claude-opus-5-5"
}

variable "embedding_provider" {
  description = "local (model baked into the image, no API key) or voyage."
  type        = string
  default     = "local"
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.small"
}

variable "redis_node_type" {
  type    = string
  default = "cache.t4g.micro"
}

variable "api_desired_count" {
  type    = number
  default = 2
}

variable "worker_desired_count" {
  type    = number
  default = 1
}

variable "deletion_protection" {
  type    = bool
  default = true
}
