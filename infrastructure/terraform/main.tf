locals {
  name            = "${var.project_name}-${var.environment}"
  pool_id         = var.existing_cognito_user_pool_id != "" ? var.existing_cognito_user_pool_id : aws_cognito_user_pool.users[0].id
  pool_arn        = "arn:${data.aws_partition.current.partition}:cognito-idp:${var.aws_region}:${data.aws_caller_identity.current.account_id}:userpool/${local.pool_id}"
  frontend_origin = var.frontend_domain != "" ? "https://${var.frontend_domain}" : "https://${aws_cloudfront_distribution.frontend.domain_name}"
  common_env = merge({
    GOOGLE_SHEET_ID             = var.google_sheet_id
    GOOGLE_SHEET_GID            = var.google_sheet_gid
    MEMBER_NEETO_FORM_ID        = var.member_neeto_form_id
    MEMBER_NEETO_STATUS_FIELD   = var.member_neeto_status_field
    MEMBER_NEETO_STATUS_VALUE   = var.member_neeto_status_value
    MEMBER_TABLE_NAME           = aws_dynamodb_table.member_details.name
    PROFILE_TABLE_NAME          = aws_dynamodb_table.profiles.name
    JOB_TABLE_NAME              = aws_dynamodb_table.jobs.name
    PROFILE_BUCKET_NAME         = aws_s3_bucket.documents.id
    NEETO_SECRET_ARN            = aws_secretsmanager_secret.neeto.arn
    NEETO_API_BASE_URL          = var.neetform_api_base_url
    NEETO_FORM_ID               = var.neetform_form_id
    NEETO_ATTACHMENT_HOSTS      = join(",", var.neeto_attachment_hosts)
    MAX_PROFILE_FILE_SIZE_MB    = tostring(var.max_profile_file_size_mb)
    DOCUMENT_URL_EXPIRY_SECONDS = tostring(var.document_url_expiry_seconds)
    COGNITO_CLIENT_ID           = aws_cognito_user_pool_client.frontend.id
    COGNITO_REQUIRED_GROUP      = var.required_group
    SYNC_FUNCTION_NAME          = "${local.name}-worker"
  }, { for key, value in var.neeto_field_mapping : "NEETO_FIELD_${upper(key)}" => value })
}
resource "aws_secretsmanager_secret" "neeto" {
  name                    = "${local.name}/neetoform"
  description             = "Server-only NEETO_API_KEY and NEETO_WEBHOOK_SECRET JSON. Values initialized outside Terraform."
  recovery_window_in_days = 30
}
