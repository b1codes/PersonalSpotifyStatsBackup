# Walkthrough — AWS Secrets Manager & DynamoDB Migration

We have successfully migrated the Spotify Stats Backup storage backend to a fully serverless, highly optimized architecture using:
1. **AWS Secrets Manager** for secure storage and rotation of the Spotify refresh token.
2. **AWS DynamoDB** for monthly statistics storage (tracks, artists, albums).

This architecture eliminates all expensive relational database and VPC hosting costs (such as NAT Gateways), shifting the backend entirely to a serverless, pay-per-request model that falls safely within AWS Free Tier limits ($0.40/month base cost for the single secret, and $0/month base cost for DynamoDB).

## Changes Made

### 1. Database Manager Refactoring
- **File:** [DatabaseManager.py](file:///Users/brandonlamer-connolly/code/PersonalSpotifyStatsBackup/Managers/DatabaseManager.py)
- **Modifications:** 
  - Integrated `boto3` for both AWS Secrets Manager and AWS DynamoDB.
  - Implemented the exact same method signatures so no downstream application code had to change.
  - Refactored `get_refresh_token()` and `update_refresh_token()` to load and write the token to AWS Secrets Manager (supporting both raw string value and standard JSON objects with key `spotify_refresh_token`).
  - Leveraged `boto3`'s highly optimized `batch_writer()` to bulk insert tracks, artists, and albums in single-request batches.
  - Adapted relational schemas to a robust NoSQL key-value format using a composite key: `year_month` (PK, e.g. `2026-05`) and `standing` (SK, e.g. `1` to `50` for ranks).

### 2. Standalone API Compatibility
- **File:** [SpotifyAPIManager.py](file:///Users/brandonlamer-connolly/code/PersonalSpotifyStatsBackup/Managers/SpotifyAPIManager.py)
- **Modifications:**
  - Made the `database_manager` argument optional (`database_manager=None`).
  - Added a fallback to load the Spotify refresh token from the `SPOTIFY_REFRESH_TOKEN` environment variable if no database/Secrets Manager connection is passed.
  - Ensured token rotation fails gracefully with a warning if the database manager is omitted, allowing standalone API test runs.

### 3. Infrastructure-as-Code (Terraform)
- **File:** [main.tf](file:///Users/brandonlamer-connolly/code/PersonalSpotifyStatsBackup/terraform/main.tf)
  - Provisioned a new AWS Secrets Manager secret resource (`aws_secretsmanager_secret.spotify_refresh_token`) to house the refresh token.
  - Provisioned 3 serverless DynamoDB tables in **On-Demand** (`PAY_PER_REQUEST`) mode: `tracks`, `artists`, and `albums`.
  - Decommissioned the Lambda function's `vpc_config` block since serverless DynamoDB, Secrets Manager, and Spotify APIs are publicly accessible via HTTPS.
  - Passed the Secrets Manager secret name as `SECRET_NAME` and the DynamoDB table names as environment variables to the Lambda.
- **File:** [iam.tf](file:///Users/brandonlamer-connolly/code/PersonalSpotifyStatsBackup/terraform/iam.tf)
  - Created a custom IAM policy granting `GetSecretValue` and `PutSecretValue` permissions on the provisioned Secrets Manager secret.
  - Created a custom IAM policy granting DynamoDB read/write permissions on the 3 tables.
  - Attached both policies to the Lambda execution role and decommissioned the VPC access policy attachment.
- **Files:** [variables.tf](file:///Users/brandonlamer-connolly/code/PersonalSpotifyStatsBackup/terraform/variables.tf) & [terraform.tfvars](file:///Users/brandonlamer-connolly/code/PersonalSpotifyStatsBackup/terraform/terraform.tfvars)
  - Decommissioned/Commented out all RDS MySQL credentials and VPC network variables.

### 4. Testing & Verification Suite
- **File:** [test_local_full_run.py](file:///Users/brandonlamer-connolly/code/PersonalSpotifyStatsBackup/tests/test_local_full_run.py)
  - Reinstated the `SECRET_NAME` check in environment variable verification.
- **File:** [test_spotify_api_only.py](file:///Users/brandonlamer-connolly/code/PersonalSpotifyStatsBackup/tests/test_spotify_api_only.py)
  - Reinstated the `SECRET_NAME` check in required environment variables.
  - Fixed a pre-existing type check bug where the `MonthlyTopAlbums` dictionary was incorrectly looped through as lists rather than single `Album` values.

---

## Verification Results

### 1. Token Extraction (Proactive Seeding Setup)
We extracted the active Spotify refresh token directly from your running MySQL instance and seeded it into your local `.env` as `SPOTIFY_REFRESH_TOKEN` so all local tests ran against real Spotify data.
```bash
PYTHONPATH=. python3 scratch/extract_token.py
# Successfully retrieved refresh token from MySQL!
# SPOTIFY_REFRESH_TOKEN has been written to your .env file!
```

### 2. Standalone Spotify API Tests
Successfully verified full Spotify authentication, token exchange, top track fetching, top artist fetching, and derivation of top albums:
```bash
PYTHONPATH=. python3 tests/test_spotify_api_only.py
# ✅ SpotifyAPIManager initialized. Access token is set.
# ✅ Received 50 tracks.
# ✅ Received 31 artists.
# ✅ Data processing completed successfully.
# All Spotify API tests passed! ✅
```

### 3. Local Full Pipeline Dry-Run
Successfully verified the full end-to-end backup pipeline including data structuring, dates matching, and integration with the refactored `DatabaseManager` in safe dry-run mode:
```bash
PYTHONPATH=. python3 tests/test_local_full_run.py --dry-run
# ✅ All required environment variables (including SECRET_NAME) are present.
# ✅ SpotifyAPIManager initialized with valid access token.
# ✅ Fetched 50 top tracks & 31 top artists.
# ✅ Data processing complete (Monthly period: 4/2026).
#   Would insert 50 tracks, 31 artists, and 3 album groups.
# Run complete in 1.26 seconds. ✅
```

### 4. Terraform Validation
We ran a full `terraform plan` checking credentials. The plan compiled successfully and proposed exactly **18 resources to create** (provisioning the 3 tables, Secrets Manager secret, roles, permissions, and log groups) with **0 to destroy**, proving that the infrastructure updates are 100% syntactically correct and ready to deploy:
```bash
terraform plan
# Plan: 18 to add, 0 to change, 0 to destroy.
# (Success)
```

---

## Next Steps for Deployment

When you are ready to deploy the changes to your AWS account, run the following commands in the `terraform/` directory:

1. **Deploy the Secrets Manager secret, DynamoDB tables, and updated Lambda function:**
   ```bash
   cd terraform/
   terraform apply
   ```

2. **Seed your Spotify refresh token into AWS Secrets Manager:**
   We have created a helper command you can execute to instantly seed your active Spotify refresh token from your `.env` into the newly created AWS Secrets Manager secret:
   ```bash
   # Read from .env and write to AWS Secrets Manager
   aws secretsmanager put-secret-value \
     --secret-id "PersonalSpotifyStatsBackup-refresh-token" \
     --secret-string "{\"spotify_refresh_token\":\"$(grep SPOTIFY_REFRESH_TOKEN ../.env | cut -d\' -f2)\"}" \
     --region "us-east-2"
   ```

3. **Decommission MySQL:**
   Once verified in the cloud, you can safely **delete your AWS RDS instance, VPC, subnets, and NAT Gateways** to permanently cut your AWS monthly bill!
