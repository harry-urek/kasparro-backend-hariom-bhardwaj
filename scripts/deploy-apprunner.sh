#!/bin/bash
# =============================================================================
# AWS App Runner Quick Deploy Script
# =============================================================================
#
# Prerequisites:
#   - AWS CLI configured with appropriate credentials
#   - Docker installed and running
#   - jq installed (for JSON parsing)
#
# Usage:
#   ./scripts/deploy-apprunner.sh
#
# =============================================================================

set -e

# Configuration
REGION="${AWS_REGION:-us-east-1}"
SERVICE_NAME="${SERVICE_NAME:-kasparro-api}"
ECR_REPO="${ECR_REPO:-kasparro-backend}"

echo "=============================================="
echo "  Kasparro Backend - App Runner Deployment"
echo "=============================================="
echo ""

# Get AWS Account ID
echo "📋 Getting AWS Account ID..."
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "   Account: ${ACCOUNT_ID}"
echo "   Region: ${REGION}"
echo ""

# Create ECR repository (ignore if exists)
echo "📦 Creating ECR repository..."
aws ecr create-repository \
    --repository-name ${ECR_REPO} \
    --region ${REGION} \
    --image-scanning-configuration scanOnPush=true \
    2>/dev/null || echo "   Repository already exists"

ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO}"
echo "   ECR URI: ${ECR_URI}"
echo ""

# Login to ECR
echo "🔐 Logging into ECR..."
aws ecr get-login-password --region ${REGION} | \
    docker login --username AWS --password-stdin ${ECR_URI}
echo ""

# Build Docker image
echo "🔨 Building Docker image..."
docker build -t ${ECR_REPO} .
echo ""

# Tag and push
echo "📤 Pushing image to ECR..."
docker tag ${ECR_REPO}:latest ${ECR_URI}:latest
docker push ${ECR_URI}:latest
echo ""

# Get the image digest
IMAGE_DIGEST=$(aws ecr describe-images \
    --repository-name ${ECR_REPO} \
    --region ${REGION} \
    --query 'sort_by(imageDetails,& imagePushedAt)[-1].imageDigest' \
    --output text)

echo "✅ Image pushed successfully!"
echo ""
echo "=============================================="
echo "  Deployment Complete"
echo "=============================================="
echo ""
echo "📌 Image Details:"
echo "   Repository: ${ECR_URI}"
echo "   Tag: latest"
echo "   Digest: ${IMAGE_DIGEST}"
echo ""
echo "🚀 Next Steps:"
echo ""
echo "1. Go to AWS App Runner console:"
echo "   https://${REGION}.console.aws.amazon.com/apprunner/home?region=${REGION}#/services"
echo ""
echo "2. Click 'Create service'"
echo ""
echo "3. Configure source:"
echo "   - Source: Container registry → Amazon ECR"
echo "   - Image URI: ${ECR_URI}:latest"
echo "   - Deployment trigger: Automatic"
echo ""
echo "4. Configure service:"
echo "   - Service name: ${SERVICE_NAME}"
echo "   - CPU: 1 vCPU"
echo "   - Memory: 2 GB"
echo "   - Port: 8000"
echo ""
echo "5. Add environment variables:"
echo "   DATABASE_URL=postgresql+psycopg2://user:pass@rds-endpoint:5432/kasparro"
echo "   ENV=prod"
echo "   LOG_LEVEL=INFO"
echo "   ETL_ENABLED=false"
echo ""
echo "6. Configure networking:"
echo "   - Create VPC connector to access RDS"
echo "   - Select same VPC/subnets as RDS"
echo ""
echo "7. Deploy and get your URL!"
echo ""
echo "=============================================="
