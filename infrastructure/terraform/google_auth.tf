locals {
  google_configured = var.enable_google_login && var.google_client_id != ""
  oauth_domain      = var.enable_google_login ? "${aws_cognito_user_pool_domain.google[0].domain}.auth.${var.aws_region}.amazoncognito.com" : ""
}

resource "aws_cognito_user_pool_domain" "google" {
  count        = var.enable_google_login ? 1 : 0
  domain       = "${local.name}-${data.aws_caller_identity.current.account_id}"
  user_pool_id = local.pool_id
}

data "aws_secretsmanager_secret_version" "google" {
  count     = local.google_configured ? 1 : 0
  secret_id = var.google_oauth_secret_arn
  lifecycle {
    precondition {
      condition     = var.google_oauth_secret_arn != ""
      error_message = "Google login requires a Secrets Manager ARN containing client_secret."
    }
  }
}

resource "aws_cognito_identity_provider" "google" {
  count         = local.google_configured ? 1 : 0
  user_pool_id  = local.pool_id
  provider_name = "Google"
  provider_type = "Google"
  provider_details = {
    client_id        = var.google_client_id
    client_secret    = jsondecode(data.aws_secretsmanager_secret_version.google[0].secret_string).client_secret
    authorize_scopes = "openid email profile"
  }
  attribute_mapping = {
    username       = "sub"
    email          = "email"
    email_verified = "email_verified"
    name           = "name"
  }
  # Cognito fills these Google endpoints automatically. Keep credentials and
  # scopes managed by Terraform while preserving the service-owned defaults.
  lifecycle {
    ignore_changes = [
      provider_details["attributes_url"],
      provider_details["attributes_url_add_attributes"],
      provider_details["authorize_url"],
      provider_details["oidc_issuer"],
      provider_details["token_request_method"],
      provider_details["token_url"],
    ]
  }
}

output "cognito_oauth_domain" { value = local.oauth_domain }
output "google_login_enabled" { value = local.google_configured }
output "google_redirect_uri" {
  value = var.enable_google_login ? "https://${local.oauth_domain}/oauth2/idpresponse" : ""
}
