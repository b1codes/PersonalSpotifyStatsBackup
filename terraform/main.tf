# =============================================================================
# Terraform Configuration
# =============================================================================

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# =============================================================================
# Lambda Layer — Python Dependencies
# =============================================================================
# Packages requirements.txt into a Lambda Layer so dependency updates are
# separate from code deploys. Lambda Layers are free — you only pay for the
# Lambda execution time (which stays the same).

resource "null_resource" "install_dependencies" {
  # Re-run whenever requirements.txt changes
  triggers = {
    requirements_hash = filemd5("${path.module}/../requirements.txt")
  }

  provisioner "local-exec" {
    command = <<-EOT
      rm -rf ${path.module}/layer_build
      mkdir -p ${path.module}/layer_build/python
      uv pip install \
        --target ${path.module}/layer_build/python \
        --requirement ${path.module}/../requirements.txt \
        --python-version 3.12 \
        --quiet
    EOT
  }
}

data "archive_file" "lambda_layer" {
  type        = "zip"
  source_dir  = "${path.module}/layer_build"
  output_path = "${path.module}/.build/layer.zip"

  depends_on = [null_resource.install_dependencies]
}

resource "aws_lambda_layer_version" "dependencies" {
  layer_name          = "${var.lambda_function_name}-deps"
  filename            = data.archive_file.lambda_layer.output_path
  source_code_hash    = data.archive_file.lambda_layer.output_base64sha256
  compatible_runtimes = [var.lambda_runtime]
  description         = "Python dependencies for ${var.lambda_function_name}"
}

# =============================================================================
# Lambda Function — Application Code
# =============================================================================

data "archive_file" "lambda_code" {
  type        = "zip"
  output_path = "${path.module}/.build/lambda_code.zip"

  source_dir = "${path.module}/.."

  excludes = [
    ".git",
    ".gitignore",
    ".env",
    ".DS_Store",
    "__pycache__",
    "tests",
    "build",
    "terraform",
    "main.py",
    "SpotifyRefreshTokenGenerator.py",
    "Bastion Key.pem",
    "sample.env",
    "README.md",
    "LICENSE",
    "SpotifyStatsEnv",
    "bin",
    ".gemini",
    ".agents",
    "authorization.txt",
    "spotify_data",
    "scratch",
    "docs",
    "scripts",
    "import_history.py",
    "CLAUDE.md",
    # Exclude vendored dependencies (they go in the Layer now)
    "boto3",
    "boto3-1.28.66.dist-info",
    "botocore",
    "botocore-1.31.85.dist-info",
    "certifi",
    "certifi-2025.7.14.dist-info",
    "charset_normalizer",
    "charset_normalizer-3.4.2.dist-info",
    "dateutil",
    "python_dateutil-2.9.0.post0.dist-info",
    "dotenv",
    "python_dotenv-1.0.1.dist-info",
    "google",
    "idna",
    "idna-3.10.dist-info",
    "jmespath",
    "jmespath-1.0.1.dist-info",
    "requests",
    "requests-2.32.3.dist-info",
    "s3transfer",
    "s3transfer-0.7.0.dist-info",
    "six.py",
    "six-1.17.0.dist-info",
    "urllib3",
    "urllib3-2.0.7.dist-info",
  ]
}

resource "aws_lambda_function" "spotify_backup" {
  function_name    = var.lambda_function_name
  role             = aws_iam_role.lambda_execution_role.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = var.lambda_runtime
  timeout          = var.lambda_timeout
  memory_size      = var.lambda_memory_size
  filename         = data.archive_file.lambda_code.output_path
  source_code_hash = data.archive_file.lambda_code.output_base64sha256

  layers = [aws_lambda_layer_version.dependencies.arn]

  environment {
    variables = {
      CLIENT_ID              = var.spotify_client_id
      CLIENT_SECRET          = var.spotify_client_secret
      REDIRECT_URI           = var.spotify_redirect_uri
      SECRET_NAME            = aws_secretsmanager_secret.spotify_refresh_token.name
      DYNAMODB_TABLE_TRACKS  = aws_dynamodb_table.tracks.name
      DYNAMODB_TABLE_ARTISTS = aws_dynamodb_table.artists.name
      DYNAMODB_TABLE_ALBUMS  = aws_dynamodb_table.albums.name
      DYNAMODB_TABLE_GENRES  = aws_dynamodb_table.genres.name
    }
  }

  tags = {
    Project = var.lambda_function_name
  }
}

# =============================================================================
# CloudWatch Log Group
# =============================================================================

resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${var.lambda_function_name}"
  retention_in_days = var.log_retention_days

  tags = {
    Project = var.lambda_function_name
  }
}

# =============================================================================
# DynamoDB Tables — Backup Storage Backend
# =============================================================================

resource "aws_secretsmanager_secret" "spotify_refresh_token" {
  name                    = "${var.lambda_function_name}-refresh-token"
  description             = "Spotify Refresh Token for stats backup"
  recovery_window_in_days = 0

  tags = {
    Project = var.lambda_function_name
  }
}

resource "aws_dynamodb_table" "tracks" {
  name         = "${var.lambda_function_name}-tracks"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "year_month"
  range_key    = "standing"

  attribute {
    name = "year_month"
    type = "S"
  }

  attribute {
    name = "standing"
    type = "N"
  }

  tags = {
    Project = var.lambda_function_name
  }
}

resource "aws_dynamodb_table" "artists" {
  name         = "${var.lambda_function_name}-artists"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "year_month"
  range_key    = "standing"

  attribute {
    name = "year_month"
    type = "S"
  }

  attribute {
    name = "standing"
    type = "N"
  }

  tags = {
    Project = var.lambda_function_name
  }
}

resource "aws_dynamodb_table" "albums" {
  name         = "${var.lambda_function_name}-albums"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "year_month"
  range_key    = "standing"

  attribute {
    name = "year_month"
    type = "S"
  }

  attribute {
    name = "standing"
    type = "N"
  }

  tags = {
    Project = var.lambda_function_name
  }
}

resource "aws_dynamodb_table" "genres" {
  name         = "${var.lambda_function_name}-genres"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "year_month"
  range_key    = "standing"

  attribute {
    name = "year_month"
    type = "S"
  }

  attribute {
    name = "standing"
    type = "N"
  }

  tags = {
    Project = var.lambda_function_name
  }
}
