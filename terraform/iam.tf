# =============================================================================
# IAM — Lambda Execution Role & Policies
# =============================================================================

# Trust policy: allow Lambda service to assume this role
data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "lambda_execution_role" {
  name               = "${var.lambda_function_name}-execution-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json

  tags = {
    Project = var.lambda_function_name
  }
}

# ---------- Managed policy: VPC access ----------
# DECOMMISSIONED: DynamoDB does not require VPC access.
# resource "aws_iam_role_policy_attachment" "lambda_vpc_access" {
#   role       = aws_iam_role.lambda_execution_role.name
#   policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
# }

# ---------- Custom policy: CloudWatch Logs ----------
data "aws_iam_policy_document" "lambda_logging" {
  statement {
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = [
      "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${var.lambda_function_name}:*"
    ]
  }
}

resource "aws_iam_policy" "lambda_logging" {
  name   = "${var.lambda_function_name}-logging"
  policy = data.aws_iam_policy_document.lambda_logging.json
}

resource "aws_iam_role_policy_attachment" "lambda_logging" {
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = aws_iam_policy.lambda_logging.arn
}

# ---------- Custom policy: DynamoDB access ----------
data "aws_iam_policy_document" "lambda_dynamodb" {
  statement {
    effect = "Allow"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
      "dynamodb:BatchWriteItem",
      "dynamodb:Query",
      "dynamodb:Scan"
    ]
    resources = [
      aws_dynamodb_table.tracks.arn,
      aws_dynamodb_table.artists.arn,
      aws_dynamodb_table.albums.arn,
      aws_dynamodb_table.genres.arn
    ]
  }
}

resource "aws_iam_policy" "lambda_dynamodb" {
  name   = "${var.lambda_function_name}-dynamodb"
  policy = data.aws_iam_policy_document.lambda_dynamodb.json
}

resource "aws_iam_role_policy_attachment" "lambda_dynamodb" {
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = aws_iam_policy.lambda_dynamodb.arn
}

# ---------- Custom policy: Secrets Manager access ----------
data "aws_iam_policy_document" "lambda_secrets" {
  statement {
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:PutSecretValue"
    ]
    resources = [
      aws_secretsmanager_secret.spotify_refresh_token.arn
    ]
  }
}

resource "aws_iam_policy" "lambda_secrets" {
  name   = "${var.lambda_function_name}-secrets"
  policy = data.aws_iam_policy_document.lambda_secrets.json
}

resource "aws_iam_role_policy_attachment" "lambda_secrets" {
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = aws_iam_policy.lambda_secrets.arn
}
