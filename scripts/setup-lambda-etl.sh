#!/bin/bash
# =============================================================================
# Setup Lambda ETL Trigger with EventBridge Schedule
# =============================================================================
#
# This script creates:
#   1. IAM role for Lambda execution
#   2. Lambda function for ETL triggering
#   3. EventBridge rule for scheduled execution
#
# Prerequisites:
#   - AWS CLI configured
#   - App Runner service URL
#
# Usage:
#   ./scripts/setup-lambda-etl.sh <app-runner-url>
#
# Example:
#   ./scripts/setup-lambda-etl.sh https://xxx.us-east-1.awsapprunner.com
#
# =============================================================================

set -e

# Check arguments
if [ -z "$1" ]; then
    echo "Usage: $0 <app-runner-url>"
    echo "Example: $0 https://xxx.us-east-1.awsapprunner.com"
    exit 1
fi

API_URL="$1"
REGION="${AWS_REGION:-us-east-1}"
FUNCTION_NAME="kasparro-etl-trigger"
ROLE_NAME="kasparro-etl-lambda-role"
RULE_NAME="kasparro-etl-schedule"
SCHEDULE="rate(5 minutes)"  # Every 5 minutes

echo "=============================================="
echo "  Lambda ETL Trigger Setup"
echo "=============================================="
echo ""
echo "API URL: ${API_URL}"
echo "Region: ${REGION}"
echo ""

# Get AWS Account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Create IAM role trust policy
echo "📋 Creating IAM role..."
cat > /tmp/trust-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "lambda.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}
EOF

# Create role (ignore if exists)
aws iam create-role \
    --role-name ${ROLE_NAME} \
    --assume-role-policy-document file:///tmp/trust-policy.json \
    2>/dev/null || echo "   Role already exists"

# Attach basic execution policy
aws iam attach-role-policy \
    --role-name ${ROLE_NAME} \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole \
    2>/dev/null || true

ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"
echo "   Role ARN: ${ROLE_ARN}"
echo ""

# Wait for role to propagate
echo "⏳ Waiting for IAM role to propagate..."
sleep 10

# Package Lambda function
echo "📦 Packaging Lambda function..."
cd lambda
zip -j /tmp/etl_trigger.zip etl_trigger.py
cd ..
echo ""

# Create or update Lambda function
echo "🔧 Creating/Updating Lambda function..."
if aws lambda get-function --function-name ${FUNCTION_NAME} --region ${REGION} 2>/dev/null; then
    # Update existing function
    aws lambda update-function-code \
        --function-name ${FUNCTION_NAME} \
        --zip-file fileb:///tmp/etl_trigger.zip \
        --region ${REGION}
    
    aws lambda update-function-configuration \
        --function-name ${FUNCTION_NAME} \
        --timeout 300 \
        --environment "Variables={API_URL=${API_URL},ETL_TIMEOUT=300}" \
        --region ${REGION}
else
    # Create new function
    aws lambda create-function \
        --function-name ${FUNCTION_NAME} \
        --runtime python3.11 \
        --handler etl_trigger.lambda_handler \
        --role ${ROLE_ARN} \
        --zip-file fileb:///tmp/etl_trigger.zip \
        --timeout 300 \
        --memory-size 128 \
        --environment "Variables={API_URL=${API_URL},ETL_TIMEOUT=300}" \
        --region ${REGION}
fi

LAMBDA_ARN="arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:${FUNCTION_NAME}"
echo "   Lambda ARN: ${LAMBDA_ARN}"
echo ""

# Create EventBridge rule
echo "⏰ Creating EventBridge schedule..."
aws events put-rule \
    --name ${RULE_NAME} \
    --schedule-expression "${SCHEDULE}" \
    --state ENABLED \
    --region ${REGION}

RULE_ARN="arn:aws:events:${REGION}:${ACCOUNT_ID}:rule/${RULE_NAME}"
echo "   Rule ARN: ${RULE_ARN}"
echo ""

# Add Lambda permission for EventBridge
echo "🔐 Adding Lambda permissions..."
aws lambda add-permission \
    --function-name ${FUNCTION_NAME} \
    --statement-id eventbridge-trigger \
    --action lambda:InvokeFunction \
    --principal events.amazonaws.com \
    --source-arn ${RULE_ARN} \
    --region ${REGION} \
    2>/dev/null || echo "   Permission already exists"

# Add Lambda as target for EventBridge rule
echo "🎯 Configuring EventBridge target..."
aws events put-targets \
    --rule ${RULE_NAME} \
    --targets "Id=1,Arn=${LAMBDA_ARN}" \
    --region ${REGION}

echo ""
echo "=============================================="
echo "  Setup Complete!"
echo "=============================================="
echo ""
echo "📌 Resources Created:"
echo "   Lambda Function: ${FUNCTION_NAME}"
echo "   EventBridge Rule: ${RULE_NAME}"
echo "   Schedule: ${SCHEDULE}"
echo ""
echo "🔍 Test the Lambda manually:"
echo "   aws lambda invoke --function-name ${FUNCTION_NAME} --region ${REGION} /tmp/response.json && cat /tmp/response.json"
echo ""
echo "📊 View logs:"
echo "   aws logs tail /aws/lambda/${FUNCTION_NAME} --follow --region ${REGION}"
echo ""
echo "=============================================="
