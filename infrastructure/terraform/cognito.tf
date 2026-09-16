resource "aws_cognito_user_pool" "users" {
  count                    = var.existing_cognito_user_pool_id == "" ? 1 : 0
  name                     = "${local.name}-users"
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]
  admin_create_user_config { allow_admin_create_user_only = false }
  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = true
    temporary_password_validity_days = 7
  }
  username_configuration { case_sensitive = false }
  deletion_protection = "ACTIVE"
  lifecycle { prevent_destroy = true }
}
resource "aws_cognito_user_pool_client" "frontend" {
  name                                 = "${local.name}-browser"
  user_pool_id                         = local.pool_id
  generate_secret                      = false
  supported_identity_providers         = local.google_configured ? ["COGNITO", aws_cognito_identity_provider.google[0].provider_name] : ["COGNITO"]
  allowed_oauth_flows_user_pool_client = local.google_configured
  allowed_oauth_flows                  = local.google_configured ? ["code"] : []
  allowed_oauth_scopes                 = local.google_configured ? ["openid", "email", "profile"] : []
  callback_urls                        = local.google_configured ? ["${local.frontend_origin}/login"] : []
  logout_urls                          = local.google_configured ? ["${local.frontend_origin}/login"] : []
  explicit_auth_flows                  = ["ALLOW_USER_SRP_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]
  prevent_user_existence_errors        = "ENABLED"
  enable_token_revocation              = true
  access_token_validity                = 15
  id_token_validity                    = 15
  refresh_token_validity               = 1
  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
}
resource "aws_cognito_user_group" "access" {
  count        = var.required_group == "" ? 0 : 1
  user_pool_id = local.pool_id
  name         = var.required_group
  description  = "Authorized Profile Library users; all members can read, sync, and download."
}
