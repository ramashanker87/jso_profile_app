variable "aws_region" {
  type    = string
  default = "eu-north-1"
}
variable "environment" {
  type    = string
  default = "prod"
  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.environment))
    error_message = "Use lowercase letters, digits and hyphens."
  }
}
variable "project_name" {
  type    = string
  default = "profile-library"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,30}$", var.project_name))
    error_message = "Use 3-31 lowercase letters, digits and hyphens."
  }
}
variable "frontend_domain" {
  type        = string
  default     = ""
  description = "Optional hostname; configure DNS separately."
}
variable "frontend_certificate_arn" {
  type        = string
  default     = ""
  description = "Existing us-east-1 ACM certificate for optional CloudFront domain."
}
variable "neetform_api_base_url" {
  type    = string
  default = ""
}
variable "neetform_form_id" {
  type    = string
  default = ""
}
variable "neeto_attachment_hosts" {
  type    = list(string)
  default = []
}
variable "neeto_field_mapping" {
  type    = map(string)
  default = { name = "name", email = "email", linkedin = "linkedin", support = "support", theme = "theme", file = "file_upload" }
}
variable "existing_cognito_user_pool_id" {
  type        = string
  default     = ""
  description = "Optional existing pool in aws_region; empty creates an administrator-only pool."
}
variable "required_group" {
  type        = string
  default     = ""
  description = "Optional application access group, useful when reusing a pool shared with another app. All members have identical permissions."
}
variable "max_profile_file_size_mb" {
  type    = number
  default = 20
  validation {
    condition     = var.max_profile_file_size_mb >= 1 && var.max_profile_file_size_mb <= 100
    error_message = "File size must be between 1 and 100 MB."
  }
}
variable "document_url_expiry_seconds" {
  type    = number
  default = 900
  validation {
    condition     = var.document_url_expiry_seconds >= 60 && var.document_url_expiry_seconds <= 900
    error_message = "Signed URLs must expire between 60 and 900 seconds."
  }
}
variable "log_retention_days" {
  type    = number
  default = 14
}
variable "enable_error_alarms" {
  type    = bool
  default = false
}
variable "lambda_zip_path" {
  type    = string
  default = "../../.build/backend.zip"
}

variable "worker_reserved_concurrency" {
  type        = number
  default     = -1
  description = "Optional worker cap; -1 uses account concurrency. DynamoDB leases protect writes in either mode."
  validation {
    condition     = var.worker_reserved_concurrency == -1 || var.worker_reserved_concurrency >= 1
    error_message = "Use -1 for unreserved concurrency or a positive limit."
  }
}

variable "google_sheet_id" {
  type        = string
  default     = ""
  description = "Optional member directory spreadsheet ID; enables Sheets manual sync."
}
variable "google_sheet_gid" {
  type    = string
  default = "1259657163"
}

variable "enable_google_login" {
  type        = bool
  default     = false
  description = "Provision the Cognito OAuth domain for Google signup/sign-in."
}
variable "google_client_id" {
  type        = string
  default     = ""
  description = "Google OAuth web application client ID."
}
variable "google_oauth_secret_arn" {
  type        = string
  default     = ""
  description = "Secrets Manager ARN containing JSON with client_secret for Google OAuth."
}

variable "member_neeto_form_id" {
  type    = string
  default = ""
}
variable "member_neeto_status_field" {
  type    = string
  default = ""
}
variable "member_neeto_status_value" {
  type    = string
  default = ""
}
