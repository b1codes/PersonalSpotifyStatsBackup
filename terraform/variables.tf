# =============================================================================
# Variables
# =============================================================================

# --- AWS Configuration ---

variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "us-east-2"
}

# --- Lambda Configuration ---

variable "lambda_function_name" {
  description = "Name of the Lambda function."
  type        = string
  default     = "PersonalSpotifyStatsBackup"
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds."
  type        = number
  default     = 60
}

variable "lambda_memory_size" {
  description = "Lambda function memory in MB."
  type        = number
  default     = 256
}

variable "lambda_runtime" {
  description = "Lambda runtime (Python version)."
  type        = string
  default     = "python3.9"
}

# --- Networking (VPC) ---
# TODO: Fill these in with your actual AWS VPC/subnet/security group IDs.
# You can find these in the AWS Console under VPC > Subnets and Security Groups,
# or by running:
#   aws ec2 describe-vpcs --query 'Vpcs[*].[VpcId,Tags]'
#   aws ec2 describe-subnets --query 'Subnets[*].[SubnetId,VpcId,AvailabilityZone]'
#   aws ec2 describe-security-groups --query 'SecurityGroups[*].[GroupId,GroupName,VpcId]'

# DECOMMISSIONED: VPC variables are not needed for DynamoDB.
# variable "vpc_id" {
#   description = "TODO: The ID of your existing VPC (e.g. vpc-0abc1234def56789)."
#   type        = string
# }

# variable "subnet_ids" {
#   description = "TODO: List of private subnet IDs the Lambda runs in (e.g. [\"subnet-aaa\", \"subnet-bbb\"])."
#   type        = list(string)
# }

# variable "security_group_ids" {
#   description = "TODO: List of security group IDs for the Lambda (e.g. [\"sg-0abc1234\"])."
#   type        = list(string)
# }

# --- Spotify API ---

variable "spotify_client_id" {
  description = "Spotify application Client ID."
  type        = string
  sensitive   = true
}

variable "spotify_client_secret" {
  description = "Spotify application Client Secret."
  type        = string
  sensitive   = true
}

variable "spotify_redirect_uri" {
  description = "Spotify application Redirect URI."
  type        = string
}

# --- Database ---
# DECOMMISSIONED: MySQL database variables are not needed for DynamoDB.
# variable "db_host" {
#   description = "MySQL database hostname."
#   type        = string
# }

# variable "db_username" {
#   description = "MySQL database username."
#   type        = string
# }

# variable "db_password" {
#   description = "MySQL database password."
#   type        = string
#   sensitive   = true
# }

# variable "db_name" {
#   description = "MySQL database name."
#   type        = string
#   default     = "spotify_stats"
# }

# variable "db_port" {
#   description = "MySQL database port."
#   type        = string
#   default     = "3306"
# }

# --- EventBridge Schedule ---

variable "schedule_expression" {
  description = "EventBridge cron/rate expression for triggering the Lambda. Default: 1st of each month at 12PM EST (17:00 UTC)."
  type        = string
  default     = "cron(0 17 1 * ? *)"
}

# --- CloudWatch ---

variable "log_retention_days" {
  description = "Number of days to retain Lambda CloudWatch logs."
  type        = number
  default     = 30
}
