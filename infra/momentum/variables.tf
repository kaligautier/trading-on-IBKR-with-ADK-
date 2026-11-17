variable "project_id" {
  type = string
  validation {
    condition     = var.project_id == "preprod-deep-copy"
    error_message = "This rollout targets the reviewed preprod project only."
  }
}
variable "region" {
  type    = string
  default = "europe-west1"
}
variable "image" {
  type    = string
  default = ""
  validation {
    condition     = var.image == "" || can(regex("@sha256:[a-f0-9]{64}$", var.image))
    error_message = "Pin the deployed image by immutable sha256 digest."
  }
}
variable "gateway_url" {
  description = "Root HTTPS origin of the private LiteLLM gateway."
  type        = string
  nullable    = false
  validation {
    condition = (
      can(regex("^https://[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*/?$", var.gateway_url)) &&
      length(trimsuffix(trimprefix(var.gateway_url, "https://"), "/")) <= 253
    )
    error_message = "Use a root HTTPS URL with a valid DNS hostname (labels up to 63 characters, hostname up to 253) and no credentials, path, query or fragment."
  }
}
variable "model" {
  type    = string
  default = "gemini-3.8-flash"
}
variable "llm_key_version" {
  type    = string
  default = "1"
  validation {
    condition     = can(regex("^[1-9][0-9]*$", var.llm_key_version))
    error_message = "Pin a positive numeric Secret Manager version."
  }
}
variable "session_database_version" {
  type    = string
  default = "1"
  validation {
    condition     = can(regex("^[1-9][0-9]*$", var.session_database_version))
    error_message = "Pin a positive numeric Secret Manager version."
  }
}
variable "result_database_version" {
  type    = string
  default = "1"
  validation {
    condition     = can(regex("^[1-9][0-9]*$", var.result_database_version))
    error_message = "Pin a positive numeric Secret Manager version."
  }
}
