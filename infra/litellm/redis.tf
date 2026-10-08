# External Aiven Valkey / Redis. Upload credentials outside Terraform.
variable "redis_connection" {
  description = "Optional shared TLS Redis endpoint and pinned secret versions. No service is provisioned here."
  type = object({
    host             = string
    port             = number
    username         = optional(string, "default")
    password_version = string
    ca_version       = optional(string)
  })
  default = null
  validation {
    condition = var.redis_connection == null ? true : (
      can(regex("^[a-zA-Z0-9][a-zA-Z0-9.-]+$", var.redis_connection.host)) &&
      var.redis_connection.port >= 1 && var.redis_connection.port <= 65535 && floor(var.redis_connection.port) == var.redis_connection.port &&
      can(regex("^[a-zA-Z0-9_-]+$", var.redis_connection.username)) &&
      can(regex("^[1-9][0-9]*$", var.redis_connection.password_version)) &&
      (var.redis_connection.ca_version == null || can(regex("^[1-9][0-9]*$", var.redis_connection.ca_version)))
    )
    error_message = "Use an explicit host, integer TCP port, username and numeric password/CA secret versions."
  }
}

resource "google_secret_manager_secret" "redis" {
  for_each            = toset(["password", "ca"])
  project             = var.project_id
  secret_id           = "litellm-redis-${each.key}"
  version_destroy_ttl = "2592000s"
  replication {
    auto {}
  }
  lifecycle { prevent_destroy = true }
}

resource "google_secret_manager_secret_iam_member" "redis" {
  for_each  = google_secret_manager_secret.redis
  project   = var.project_id
  secret_id = each.value.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

locals {
  redis_enabled    = var.redis_connection != null
  redis_ca_enabled = try(var.redis_connection.ca_version != null, false)
  redis_env = local.redis_enabled ? merge({
    REDIS_HOST               = var.redis_connection.host
    REDIS_PORT               = tostring(var.redis_connection.port)
    REDIS_USERNAME           = var.redis_connection.username
    REDIS_SSL                = "true"
    REDIS_SSL_CERT_REQS      = "required"
    REDIS_SSL_CHECK_HOSTNAME = "true"
  }, local.redis_ca_enabled ? { REDIS_SSL_CA_CERTS = "/etc/redis/ca.pem" } : {}) : {}
  redis_secret_env = local.redis_enabled ? {
    REDIS_PASSWORD = {
      secret  = google_secret_manager_secret.redis["password"].secret_id
      version = var.redis_connection.password_version
    }
  } : {}
}
