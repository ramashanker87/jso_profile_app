output "frontend_url" { value = local.frontend_origin }
output "cloudfront_url" { value = "https://${aws_cloudfront_distribution.frontend.domain_name}" }
output "cloudfront_distribution_id" { value = aws_cloudfront_distribution.frontend.id }
output "frontend_bucket_name" { value = aws_s3_bucket.frontend.id }
output "api_url" { value = aws_apigatewayv2_api.api.api_endpoint }
output "cognito_user_pool_id" { value = local.pool_id }
output "cognito_client_id" { value = aws_cognito_user_pool_client.frontend.id }
output "profile_bucket_name" { value = aws_s3_bucket.documents.id }
output "dynamodb_table_name" { value = aws_dynamodb_table.profiles.name }
output "webhook_url" { value = "${aws_apigatewayv2_api.api.api_endpoint}/webhooks/neetform" }
output "neeto_secret_arn" { value = aws_secretsmanager_secret.neeto.arn }
output "aws_region" { value = var.aws_region }
output "required_group" { value = var.required_group }

output "member_details_table_name" {
  value = aws_dynamodb_table.member_details.name
}
