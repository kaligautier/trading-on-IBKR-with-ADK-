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
variable "gateway_url" { type = string }
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
