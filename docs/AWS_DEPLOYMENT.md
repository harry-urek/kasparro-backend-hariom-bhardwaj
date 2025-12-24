# AWS App Runner Deployment Guide

Production deployment for the Crypto ETL Backend using AWS App Runner - the simplest and fastest way to deploy containerized applications on AWS.

## Table of Contents
- [Why App Runner?](#why-app-runner)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Deployment Steps](#deployment-steps)
- [Lambda ETL Scheduler](#lambda-etl-scheduler)
- [Environment Configuration](#environment-configuration)
- [Cost Comparison](#cost-comparison)
- [Monitoring & Logs](#monitoring--logs)
- [Troubleshooting](#troubleshooting)

---

## Why App Runner?

| Pros | Cons |
|------|------|
| ✅ Fastest to deploy (5-10 minutes) | ❌ Less control than ECS |
| ✅ Fully managed (no infrastructure to configure) | ❌ Slightly more expensive for always-on |
| ✅ Auto-scaling built-in | ❌ Limited networking options |
| ✅ HTTPS included by default | |
| ✅ No ALB or ECS complexity | |
| ✅ Automatic deployments from ECR/GitHub | |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Internet                             │
└────────────────────────────┬────────────────────────────────┘
                             │
                    ┌────────▼─────────┐
                    │  App Runner      │
                    │  (API Service)   │
                    │  Port: 8000      │
                    │  ENV: prod       │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │   VPC Connector  │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  RDS PostgreSQL  │
                    │  (Private)       │
                    └──────────────────┘

┌─────────────────┐         ┌──────────────────┐
│  EventBridge    │────────▶│  Lambda Function │
│  (Cron: */5min) │         │  (ETL Trigger)   │
└─────────────────┘         └────────┬─────────┘
                                     │
                            ┌────────▼─────────┐
                            │  App Runner API  │
                            │  POST /etl/run   │
                            └──────────────────┘
```

**Key Components:**
- **App Runner Service**: Hosts the FastAPI application with auto-scaling
- **RDS PostgreSQL**: Managed database in private subnet
- **VPC Connector**: Allows App Runner to access private RDS
- **Lambda + EventBridge**: Scheduled ETL triggering (since App Runner doesn't support cron)

---

## Prerequisites

1. **AWS CLI** configured with appropriate credentials
2. **Docker** installed and running
3. **AWS Account** with permissions for:
   - ECR (Elastic Container Registry)
   - App Runner
   - RDS
   - Lambda
   - EventBridge
   - IAM

---

## Deployment Steps

### Step 1: Setup RDS Database

```bash
# Via AWS Console or CLI
# Create RDS PostgreSQL instance:
#   - Engine: PostgreSQL 16
#   - Instance: db.t3.micro (free tier eligible)
#   - Database name: kasparro
#   - Username: kasparro_user
#   - Password: <secure-password>
#   - Public access: No (private subnet)
#   - VPC: Note your VPC and subnet IDs
```

### Step 2: Push Image to ECR

#### Option A: Use the deployment script

```bash
# Make script executable
chmod +x scripts/deploy-apprunner.sh

# Run deployment
./scripts/deploy-apprunner.sh
```

#### Option B: Manual steps

```bash
# Set variables
REGION="us-east-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO="kasparro-backend"

# Create ECR repository
aws ecr create-repository --repository-name ${ECR_REPO} --region ${REGION}

# Login to ECR
aws ecr get-login-password --region ${REGION} | \
    docker login --username AWS --password-stdin \
    ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com

# Build and push
docker build -t ${ECR_REPO} .
docker tag ${ECR_REPO}:latest ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO}:latest
docker push ${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO}:latest
```

### Step 3: Create App Runner Service

#### Via AWS Console:

1. Navigate to **App Runner** → **Create service**

2. **Source configuration:**
   - Source: Container registry → Amazon ECR
   - Image URI: `<account-id>.dkr.ecr.<region>.amazonaws.com/kasparro-backend:latest`
   - Deployment trigger: Automatic (recommended)

3. **Service configuration:**
   - Service name: `kasparro-api`
   - CPU: 1 vCPU
   - Memory: 2 GB
   - Port: 8000

4. **Environment variables:**
   ```
   DATABASE_URL=postgresql+psycopg2://kasparro_user:<password>@<rds-endpoint>:5432/kasparro
   ENV=prod
   LOG_LEVEL=INFO
   ETL_ENABLED=false
   COINPAPRIKA_API_KEY=<optional>
   ```

5. **Networking:**
   - Create new VPC connector
   - Select same VPC as RDS
   - Select private subnets
   - Security group: Allow outbound to RDS (port 5432)

6. Click **Create & deploy**

### Step 4: Get Your Service URL

After deployment completes (5-10 minutes):

```bash
# Your URL will be:
https://xxxxxxxxxx.<region>.awsapprunner.com

# Test health endpoint
curl https://your-url.awsapprunner.com/health
```

---

## Lambda ETL Scheduler

Since App Runner doesn't support scheduled tasks, we use Lambda + EventBridge:

### Setup using script:

```bash
chmod +x scripts/setup-lambda-etl.sh
./scripts/setup-lambda-etl.sh https://your-url.awsapprunner.com
```

### Manual setup:

1. **Create Lambda function** (`lambda/etl_trigger.py`):
   - Runtime: Python 3.11
   - Handler: `etl_trigger.lambda_handler`
   - Timeout: 300 seconds (5 minutes)
   - Memory: 128 MB
   - Environment variables:
     - `API_URL`: Your App Runner URL
     - `ETL_TIMEOUT`: 300

2. **Create EventBridge rule:**
   - Name: `kasparro-etl-schedule`
   - Schedule: `rate(5 minutes)` or `cron(0/5 * * * ? *)`
   - Target: Lambda function

### Test Lambda manually:

```bash
aws lambda invoke \
    --function-name kasparro-etl-trigger \
    --region us-east-1 \
    /tmp/response.json && cat /tmp/response.json
```

---

## Environment Configuration

### Environment Modes

The application supports two modes via the `ENV` variable:

| Setting | `ENV=dev` (Development) | `ENV=prod` (Production) |
|---------|------------------------|------------------------|
| Swagger Docs | ✅ Enabled at `/docs` | ❌ Disabled |
| ReDoc | ✅ Enabled at `/redoc` | ❌ Disabled |
| OpenAPI | ✅ Enabled | ❌ Disabled |
| Debug Mode | ✅ Enabled | ❌ Disabled |
| Log Level | As configured | Minimum INFO |

### Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+psycopg2://user:pass@host:5432/db` |
| `ENV` | Environment mode | `dev` or `prod` |

### Optional Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Logging level |
| `ETL_ENABLED` | `true` | Enable background ETL (set `false` for App Runner) |
| `ETL_INTERVAL_SECONDS` | `300` | ETL interval (when enabled) |
| `COINPAPRIKA_API_KEY` | - | CoinPaprika API key |
| `SLACK_WEBHOOK_URL` | - | Slack notifications for errors |

### Sample `.env` for Production

```env
ENV=prod
DATABASE_URL=postgresql+psycopg2://kasparro_user:SecurePass123@kasparro-db.xxxxx.us-east-1.rds.amazonaws.com:5432/kasparro
LOG_LEVEL=INFO
ETL_ENABLED=false
COINPAPRIKA_API_KEY=your-api-key
```

---

## Cost Comparison

### App Runner + Lambda + RDS

| Resource | Monthly Cost |
|----------|-------------|
| App Runner (1 vCPU, 2GB, always-on) | ~$25-40 |
| Lambda (5min intervals, ~8640 invocations) | ~$1-2 |
| RDS db.t3.micro | ~$15-20 |
| Data transfer | ~$1-5 |
| **Total** | **~$42-67/month** |

### ECS Fargate Alternative

| Resource | Monthly Cost |
|----------|-------------|
| ECS Fargate tasks | ~$20-30 |
| Application Load Balancer | ~$16-20 |
| RDS db.t3.micro | ~$15-20 |
| **Total** | **~$51-70/month** |

---

## Monitoring & Logs

### App Runner Logs (CloudWatch)

```bash
# Tail application logs
aws logs tail /aws/apprunner/kasparro-api/service --follow

# Search for errors
aws logs filter-log-events \
    --log-group-name /aws/apprunner/kasparro-api/service \
    --filter-pattern "ERROR"
```

### Lambda Logs

```bash
# Tail ETL trigger logs
aws logs tail /aws/lambda/kasparro-etl-trigger --follow
```

### Health Endpoints

```bash
# Basic health check
curl https://your-url.awsapprunner.com/health

# Detailed health with environment info
curl https://your-url.awsapprunner.com/health/detailed

# Readiness probe
curl https://your-url.awsapprunner.com/health/ready

# Liveness probe
curl https://your-url.awsapprunner.com/health/live
```

### ETL Statistics

```bash
# Check ETL run history
curl https://your-url.awsapprunner.com/stats

# Check checkpoints
curl https://your-url.awsapprunner.com/stats/checkpoints

# Source summaries
curl https://your-url.awsapprunner.com/stats/sources
```

---

## Troubleshooting

### App Runner Service Won't Start

1. **Check logs:**
   ```bash
   aws logs tail /aws/apprunner/kasparro-api/service --follow
   ```

2. **Verify environment variables** in App Runner console

3. **Check VPC connector** can reach RDS:
   - Same VPC as RDS
   - Security group allows outbound to RDS port 5432

### Database Connection Failed

1. **Verify DATABASE_URL** format:
   ```
   postgresql+psycopg2://user:password@endpoint:5432/database
   ```

2. **Check RDS security group** allows inbound from App Runner VPC connector

3. **Ensure RDS is in same VPC** as App Runner connector

### ETL Not Running

1. **Check Lambda logs:**
   ```bash
   aws logs tail /aws/lambda/kasparro-etl-trigger --follow
   ```

2. **Verify EventBridge rule** is enabled:
   ```bash
   aws events describe-rule --name kasparro-etl-schedule
   ```

3. **Test Lambda manually:**
   ```bash
   aws lambda invoke --function-name kasparro-etl-trigger /tmp/out.json && cat /tmp/out.json
   ```

### API Responding but No Data

1. **Trigger ETL manually:**
   ```bash
   curl -X POST https://your-url.awsapprunner.com/etl/run-all
   ```

2. **Check ETL stats:**
   ```bash
   curl https://your-url.awsapprunner.com/stats
   ```

---

## Quick Reference Commands

```bash
# Deploy image to ECR
./scripts/deploy-apprunner.sh

# Setup Lambda ETL scheduler
./scripts/setup-lambda-etl.sh https://your-url.awsapprunner.com

# Health check
curl https://your-url.awsapprunner.com/health

# Trigger ETL manually
curl -X POST https://your-url.awsapprunner.com/etl/run-all

# Get crypto data
curl "https://your-url.awsapprunner.com/data?limit=10"

# Check ETL stats
curl https://your-url.awsapprunner.com/stats

# View App Runner logs
aws logs tail /aws/apprunner/kasparro-api/service --follow

# View Lambda logs
aws logs tail /aws/lambda/kasparro-etl-trigger --follow
```

---

## Next Steps

1. **Custom Domain**: Add your own domain via App Runner console
2. **SSL Certificate**: Automatically handled by App Runner
3. **Auto-scaling**: Configure min/max instances in App Runner
4. **Alerts**: Set up CloudWatch alarms for errors/latency
5. **CI/CD**: Enable automatic deployments from GitHub

---

**App Runner is the fastest path to production** - you can have a fully deployed, scalable API in under 15 minutes!
