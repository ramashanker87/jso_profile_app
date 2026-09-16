resource "aws_apigatewayv2_api" "api" {
  name          = local.name
  protocol_type = "HTTP"
  cors_configuration {
    allow_origins = [local.frontend_origin]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["authorization", "content-type"]
    max_age       = 300
  }
}
resource "aws_apigatewayv2_authorizer" "cognito" {
  api_id           = aws_apigatewayv2_api.api.id
  name             = "cognito"
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]
  jwt_configuration {
    audience = [aws_cognito_user_pool_client.frontend.id]
    issuer   = "https://cognito-idp.${var.aws_region}.amazonaws.com/${local.pool_id}"
  }
}
resource "aws_apigatewayv2_integration" "api" {
  api_id                 = aws_apigatewayv2_api.api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 30000
}
resource "aws_apigatewayv2_route" "authenticated" {
  for_each             = toset(["GET /sambhav", "GET /sambhav/domain", "POST /sambhav/domain", "POST /sambhav/upload", "POST /sambhav/upload/complete", "GET /sambhav/document", "POST /members/detail", "POST /members/sync", "GET /members/sync", "GET /members/sync/{jobId}", "GET /members", "GET /members/detail", "GET /profiles", "GET /profiles/{profileId}", "GET /profiles/{profileId}/document", "POST /sync", "GET /sync", "GET /sync/{jobId}"])
  api_id               = aws_apigatewayv2_api.api.id
  route_key            = each.value
  target               = "integrations/${aws_apigatewayv2_integration.api.id}"
  authorization_type   = "JWT"
  authorizer_id        = aws_apigatewayv2_authorizer.cognito.id
  # API Gateway accepts either scope. Google OAuth issues openid; password
  # login issues Cognito's API scope. Lambda still checks token_use and group.
  authorization_scopes = local.google_configured ? ["aws.cognito.signin.user.admin", "openid"] : ["aws.cognito.signin.user.admin"]
}
resource "aws_apigatewayv2_route" "webhook" {
  api_id             = aws_apigatewayv2_api.api.id
  route_key          = "POST /webhooks/neetform"
  target             = "integrations/${aws_apigatewayv2_integration.api.id}"
  authorization_type = "NONE"
}
resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/apigateway/${local.name}"
  retention_in_days = var.log_retention_days
}
resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.api.id
  name        = "$default"
  auto_deploy = true
  default_route_settings {
    throttling_burst_limit = 20
    throttling_rate_limit  = 10
  }
  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api.arn
    format          = jsonencode({ requestId = "$context.requestId", route = "$context.routeKey", status = "$context.status", integrationStatus = "$context.integration.status" })
  }
}
resource "aws_lambda_permission" "api_gateway" {
  statement_id   = "AllowApiGateway"
  action         = "lambda:InvokeFunction"
  function_name  = aws_lambda_function.api.function_name
  principal      = "apigateway.amazonaws.com"
  source_arn     = "${aws_apigatewayv2_api.api.execution_arn}/*/*"
  source_account = data.aws_caller_identity.current.account_id
}
