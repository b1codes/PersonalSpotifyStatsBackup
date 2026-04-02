# =============================================================================
# EventBridge — Monthly Schedule
# =============================================================================

resource "aws_cloudwatch_event_rule" "monthly_trigger" {
  name                = "${var.lambda_function_name}-monthly"
  description         = "Triggers Spotify stats backup on the 1st of each month."
  schedule_expression = var.schedule_expression

  tags = {
    Project = var.lambda_function_name
  }
}

resource "aws_cloudwatch_event_target" "lambda_target" {
  rule = aws_cloudwatch_event_rule.monthly_trigger.name
  arn  = aws_lambda_function.spotify_backup.arn
}

# Allow EventBridge to invoke the Lambda function
resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.spotify_backup.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.monthly_trigger.arn
}
