# Terraform — PersonalSpotifyStatsBackup

Infrastructure-as-code for deploying the Spotify stats backup Lambda function to AWS.

## What Terraform Manages

| Resource | Description |
|---|---|
| **Lambda Function** | `PersonalSpotifyStatsBackup` — runs your backup code |
| **Lambda Layer** | Python dependencies from `requirements.txt` |
| **IAM Role + Policies** | Execution role with DynamoDB, Secrets Manager, and CloudWatch logging access |
| **EventBridge Rule** | Monthly schedule trigger (1st of each month) |
| **CloudWatch Log Group** | Lambda execution logs with configurable retention |

## Prerequisites

1. **Terraform** ≥ 1.0 — [Install guide](https://developer.hashicorp.com/terraform/install)
2. **AWS CLI** configured with credentials — `aws configure`
3. **Python + pip** (for building the Lambda Layer)

## Quick Start

```bash
cd terraform/

# 1. Initialize Terraform (downloads providers)
terraform init

# 2. Import your existing Lambda function into Terraform state
terraform import aws_lambda_function.spotify_backup PersonalSpotifyStatsBackup

# 3. Preview what Terraform will do
terraform plan

# 4. Apply changes (creates/updates resources)
terraform apply
```

## Importing Your Existing Lambda

Since you already have a Lambda function running in AWS, you need to import it into Terraform state so Terraform can manage it going forward:

```bash
# Import the Lambda function
terraform import aws_lambda_function.spotify_backup PersonalSpotifyStatsBackup

# If you already have a CloudWatch log group for it:
terraform import aws_cloudwatch_log_group.lambda_logs /aws/lambda/PersonalSpotifyStatsBackup

# After importing, run plan to see what differs:
terraform plan
```

The first `terraform plan` after import may show some differences between your existing configuration and what's defined in the `.tf` files. Review them carefully — Terraform will update the Lambda to match the config on the next `apply`.

## Deploying Code Changes

After making changes to your Python source code:

```bash
cd terraform/

# Preview changes (Terraform will detect the code hash changed)
terraform plan

# Deploy
terraform apply
```

Terraform automatically:
1. Zips your application code (excluding tests, build scripts, etc.)
2. Uploads the new zip to Lambda
3. Updates the function

## Updating Dependencies

When you change `requirements.txt`:

```bash
cd terraform/

# Terraform detects the requirements.txt hash changed and rebuilds the layer
terraform apply
```

## Configuration

All configuration lives in `terraform.tfvars` (gitignored). See `variables.tf` for descriptions of each variable.

### Key Variables

| Variable | Description | Default |
|---|---|---|
| `schedule_expression` | EventBridge cron expression | `cron(0 17 1 * ? *)` (1st of month at 12PM EST) |
| `lambda_timeout` | Function timeout (seconds) | `60` |
| `lambda_memory_size` | Function memory (MB) | `256` |
| `log_retention_days` | CloudWatch log retention | `30` |

## File Structure

```
terraform/
├── main.tf              # Provider, Lambda function, Lambda Layer, CloudWatch
├── variables.tf         # Input variable declarations
├── outputs.tf           # Useful outputs (ARNs, names)
├── iam.tf               # IAM role and policies
├── eventbridge.tf       # Monthly schedule trigger
├── data.tf              # Data sources for existing AWS resources
├── terraform.tfvars     # Your actual values (GITIGNORED)
└── README.md            # This file
```

## Costs

- **Lambda Layer**: Free — no additional cost, just a packaging mechanism
- **Lambda Function**: Pay per invocation (~1 invocation/month = negligible)
- **EventBridge**: Free tier covers up to 14M invocations/month
- **CloudWatch Logs**: First 5 GB/month free
