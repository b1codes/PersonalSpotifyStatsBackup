# =============================================================================
# Data Sources — References to existing AWS infrastructure
# =============================================================================
# These read your existing resources without managing them. Terraform will NOT
# create, modify, or destroy any of these.

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}
