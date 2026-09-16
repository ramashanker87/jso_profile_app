resource "aws_cloudwatch_log_group" "lambda" {
  for_each          = toset(["api", "worker"])
  name              = "/aws/lambda/${local.name}-${each.key}"
  retention_in_days = var.log_retention_days
}
resource "aws_lambda_function" "api" {
  function_name    = "${local.name}-api"
  role             = aws_iam_role.api.arn
  runtime          = "python3.12"
  handler          = "src.handlers.api.lambda_handler"
  filename         = var.lambda_zip_path
  source_code_hash = filebase64sha256(var.lambda_zip_path)
  memory_size      = 512
  timeout          = 30
  environment { variables = merge(local.common_env, { FRONTEND_ORIGIN = local.frontend_origin, COGNITO_USER_POOL_ID = local.pool_id, SAMBHAV_TABLE_NAME = aws_dynamodb_table.sambhav.name, JOB_OPENINGS_TABLE_NAME = aws_dynamodb_table.job_openings.name }) }
  depends_on = [aws_iam_role_policy.api]
}
resource "aws_lambda_function" "worker" {
  function_name    = "${local.name}-worker"
  role             = aws_iam_role.worker.arn
  runtime          = "python3.12"
  handler          = "src.handlers.worker.lambda_handler"
  filename         = var.lambda_zip_path
  source_code_hash = filebase64sha256(var.lambda_zip_path)
  memory_size      = 512
  timeout          = 120
  # DynamoDB leases serialize each profile/job, including webhook/manual overlaps.
  reserved_concurrent_executions = var.worker_reserved_concurrency
  environment { variables = local.common_env }
  depends_on = [aws_iam_role_policy.worker]
}
resource "aws_lambda_function_event_invoke_config" "worker" {
  function_name                = aws_lambda_function.worker.function_name
  maximum_event_age_in_seconds = 21600
  maximum_retry_attempts       = 2
}
resource "aws_cloudwatch_metric_alarm" "errors" {
  for_each            = var.enable_error_alarms ? toset(["api", "worker"]) : toset([])
  alarm_name          = "${local.name}-${each.key}-errors"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = "${local.name}-${each.key}" }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
}

# SyncRunner deliberately invokes the next checkpointed batch. Its pagination
# and no-progress limits bound the work; the default 16-call limit truncates
# larger imports before all members have been processed.
resource "aws_lambda_function_recursion_config" "worker" {
  function_name  = aws_lambda_function.worker.function_name
  recursive_loop = "Allow"
}
