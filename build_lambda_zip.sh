#!/bin/bash
# ============================================================
# Build Lambda Deployment Zip
# Packages the project into a zip file ready to upload to
# AWS Lambda. This script only creates the artifact — it does
# NOT deploy anything.
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

BUILD_DIR="build"
ZIP_NAME="lambda_deployment.zip"
ZIP_PATH="$BUILD_DIR/$ZIP_NAME"

# Ensure the build output directory exists
mkdir -p "$BUILD_DIR"

echo "🧹 Removing old deployment zip (if exists)..."
rm -f "$ZIP_PATH"

echo "📦 Creating Lambda deployment package..."

# Zip everything EXCEPT files that don't belong in the Lambda package
zip -r "$ZIP_PATH" . \
  -x ".git/*" \
  -x ".gitignore" \
  -x ".env" \
  -x ".DS_Store" \
  -x "__pycache__/*" \
  -x "*/__pycache__/*" \
  -x "tests/*" \
  -x "test_*.py" \
  -x "main.py" \
  -x "build_lambda_zip.sh" \
  -x "SpotifyRefreshTokenGenerator.py" \
  -x "Bastion Key.pem" \
  -x "sample.env" \
  -x "README.md" \
  -x "LICENSE" \
  -x "*.zip" \
  -x "build/*" \
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

ZIP_SIZE=$(du -h "$ZIP_PATH" | cut -f1)
echo ""
echo "✅ Deployment package created: $ZIP_PATH ($ZIP_SIZE)"
echo ""
echo "📋 Contents:"
unzip -l "$ZIP_PATH" | tail -n +4 | head -n -2 | awk '{print "   " $4}'
echo ""
echo "🚀 Next steps:"
echo "   1. Upload to Lambda via AWS Console, or:"
echo "   2. aws lambda update-function-code --function-name YOUR_FUNCTION_NAME --zip-file fileb://$ZIP_PATH"
