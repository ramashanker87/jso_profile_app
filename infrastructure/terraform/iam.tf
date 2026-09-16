locals {
  assume_lambda = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}
resource "aws_iam_role" "api" {
  name_prefix        = "${local.name}-api-"
  assume_role_policy = local.assume_lambda
}
resource "aws_iam_role" "worker" {
  name_prefix        = "${local.name}-worker-"
  assume_role_policy = local.assume_lambda
}
resource "aws_iam_role_policy" "api" {
  role = aws_iam_role.api.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.lambda["api"].arn}:*" },
    { Effect = "Allow", Action = ["cognito-idp:AdminGetUser"], Resource = "arn:${data.aws_partition.current.partition}:cognito-idp:${var.aws_region}:${data.aws_caller_identity.current.account_id}:userpool/${local.pool_id}" },
    { Effect = "Allow", Action = ["dynamodb:UpdateItem"], Resource = aws_dynamodb_table.member_details.arn },
    { Effect = "Allow", Action = ["dynamodb:GetItem", "dynamodb:Scan"], Resource = [aws_dynamodb_table.profiles.arn, aws_dynamodb_table.member_details.arn] },
    { Effect = "Allow", Action = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem"], Resource = aws_dynamodb_table.jobs.arn },
    { Effect = "Allow", Action = ["dynamodb:GetItem", "dynamodb:PutItem"], Resource = aws_dynamodb_table.sambhav.arn },
    { Effect = "Allow", Action = ["dynamodb:GetItem", "dynamodb:Scan", "dynamodb:PutItem", "dynamodb:DeleteItem"], Resource = aws_dynamodb_table.job_openings.arn },
    { Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"], Resource = ["${aws_s3_bucket.documents.arn}/sambhav/*", "${aws_s3_bucket.documents.arn}/job-openings/*"] },
    { Effect = "Allow", Action = ["s3:GetObject"], Resource = "${aws_s3_bucket.documents.arn}/profiles/*" },
    { Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = aws_secretsmanager_secret.neeto.arn },
    { Effect = "Allow", Action = ["lambda:InvokeFunction"], Resource = "arn:${data.aws_partition.current.partition}:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:${local.name}-worker" }
  ] })
}
resource "aws_iam_role_policy" "worker" {
  role = aws_iam_role.worker.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.lambda["worker"].arn}:*" },
    { Effect = "Allow", Action = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem"], Resource = [aws_dynamodb_table.profiles.arn, aws_dynamodb_table.jobs.arn, aws_dynamodb_table.member_details.arn] },
    { Effect = "Allow", Action = ["dynamodb:Scan", "dynamodb:DeleteItem"], Resource = aws_dynamodb_table.member_details.arn },
    { Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject"], Resource = "${aws_s3_bucket.documents.arn}/profiles/*" },
    { Effect = "Allow", Action = ["s3:ListBucket"], Resource = aws_s3_bucket.documents.arn },
    { Effect = "Allow", Action = ["secretsmanager:GetSecretValue"], Resource = aws_secretsmanager_secret.neeto.arn },
    { Effect = "Allow", Action = ["lambda:InvokeFunction"], Resource = "arn:${data.aws_partition.current.partition}:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:${local.name}-worker" }
  ] })
}
