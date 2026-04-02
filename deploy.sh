#!/bin/bash
# ============================================================
# Lambda Deployment Script
# Creates a zip file ready to upload to AWS Lambda.
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

ZIP_NAME="lambda_deployment.zip"

echo "🧹 Removing old deployment zip (if exists)..."
rm -f "$ZIP_NAME"

echo "📦 Creating Lambda deployment package..."

# Zip everything EXCEPT files that don't belong in the Lambda package
zip -r "$ZIP_NAME" . \
  -x ".git/*" \
  -x ".gitignore" \
  -x ".env" \
  -x ".DS_Store" \
  -x "__pycache__/*" \
  -x "*/__pycache__/*" \
  -x "tests/*" \
  -x "test_*.py" \
  -x "main.py" \
  -x "deploy.sh" \
  -x "SpotifyRefreshTokenGenerator.py" \
  -x "Bastion Key.pem" \
  -x "sample.env" \
  -x "README.md" \
  -x "LICENSE" \
  -x "*.zip" \
  -x ".gemini/*" \
  -x ".agents/*" \
  -x "SpotifyStatsEnv/*" \
  -x "authorization.txt" \
  -x "bin/*" \
  -x "boto3/*" \
  -x "boto3-*/*" \
  -x "botocore/*" \
  -x "botocore-*/*" \
  -x "s3transfer/*" \
  -x "s3transfer-*/*"

ZIP_SIZE=$(du -h "$ZIP_NAME" | cut -f1)
echo ""
echo "✅ Deployment package created: $ZIP_NAME ($ZIP_SIZE)"
echo ""
echo "📋 Contents:"
unzip -l "$ZIP_NAME" | tail -n +4 | head -n -2 | awk '{print "   " $4}'
echo ""
echo "🚀 Next steps:"
echo "   1. Upload to Lambda via AWS Console, or:"
echo "   2. aws lambda update-function-code --function-name YOUR_FUNCTION_NAME --zip-file fileb://$ZIP_NAME"
