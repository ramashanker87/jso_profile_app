resource "aws_dynamodb_table" "profiles" {
  name         = "${local.name}-profiles"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "profileId"
  attribute {
    name = "profileId"
    type = "S"
  }
  server_side_encryption { enabled = true }
  point_in_time_recovery { enabled = true }
  deletion_protection_enabled = true
  lifecycle { prevent_destroy = true }
}
resource "aws_dynamodb_table" "jobs" {
  name         = "${local.name}-jobs"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "jobId"
  attribute {
    name = "jobId"
    type = "S"
  }
  server_side_encryption { enabled = true }
  # Job summaries are kept; there is no automatic deletion policy.
}

resource "aws_dynamodb_table" "member_details" {
  name         = "jso-member-details"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "Email"
  attribute {
    name = "Email"
    type = "S"
  }
  server_side_encryption { enabled = true }
  point_in_time_recovery { enabled = true }
  deletion_protection_enabled = true
  lifecycle { prevent_destroy = true }
}

resource "aws_dynamodb_table" "sambhav" {
  name = "${local.name}-sambhav"
  billing_mode = "PAY_PER_REQUEST"
  hash_key = "id"
  attribute {
    name = "id"
    type = "S"
  }
  server_side_encryption { enabled = true }
  point_in_time_recovery { enabled = true }
  ttl {
    attribute_name = "expiresAt"
    enabled = true
  }
  deletion_protection_enabled = true
  lifecycle { prevent_destroy = true }
}
