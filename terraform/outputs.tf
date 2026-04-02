# =============================================================================
# Outputs
# =============================================================================

output "lambda_function_arn" {
  description = "ARN of the Lambda function."
  value       = aws_lambda_function.spotify_backup.arn
}

output "lambda_function_name" {
  description = "Name of the Lambda function."
  value       = aws_lambda_function.spotify_backup.function_name
}

output "lambda_layer_arn" {
  description = "ARN of the Lambda dependencies layer."
  value       = aws_lambda_layer_version.dependencies.arn
}

output "eventbridge_rule_arn" {
  description = "ARN of the EventBridge monthly schedule rule."
  value       = aws_cloudwatch_event_rule.monthly_trigger.arn
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group for Lambda execution logs."
  value       = aws_cloudwatch_log_group.lambda_logs.name
}

output "lambda_execution_role_arn" {
  description = "ARN of the Lambda execution IAM role."
  value       = aws_iam_role.lambda_execution_role.arn
}
