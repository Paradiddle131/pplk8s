variable "project" {
  description = "The lab project's id (GCP_PROJECT)."
  type        = string
}

variable "region" {
  description = "Where every regional resource lives: us-central1, where each Always Free tier applies (SL-13)."
  type        = string
  default     = "us-central1"

  validation {
    condition     = var.region == "us-central1"
    error_message = "The free tiers meet in us-central1 (semantic/PLAN.md SL-13)."
  }
}

variable "kill_switch_usd" {
  description = "Month-to-date cost after credits at which the kill switch unlinks billing. The first cent is for alerts and stopping sessions; this is for a runaway (platform/gcp/README.md)."
  type        = number
  default     = 5

  validation {
    condition     = var.kill_switch_usd > 0 && var.kill_switch_usd <= 20
    error_message = "Keep the kill switch between 0 and 20 USD."
  }
}

variable "images" {
  description = "Workload image key (workloads.yaml `image`: semantic-agent, dbt) => its reference in the lab's Artifact Registry repository. A workload exists only while its image is named here: tofu.sh passes IMAGES, else the images deployed now, so a plain gcp-up neither creates nor removes one."
  type        = map(string)
  default     = {}

  validation {
    condition     = alltrue([for k in keys(var.images) : contains(["semantic-agent", "dbt"], k)])
    error_message = "images takes the keys semantic-agent and dbt (platform/gcp/workloads.yaml)."
  }
}
