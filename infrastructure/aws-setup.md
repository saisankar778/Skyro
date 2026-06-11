# Skyro — AWS Infrastructure Setup Guide

This guide walks you through provisioning all AWS services for the Skyro drone delivery production environment.

> **For local dev, use Docker Compose** — just run `docker-compose up` and the local postgres + redis containers start automatically with the schema seeded.

---

## Prerequisites
- AWS Account with admin IAM permissions
- AWS CLI installed and configured (`aws configure`)
- Docker + Docker Compose installed locally

---

## Step 1 — Amazon RDS (PostgreSQL)

### Create the database
1. Open **RDS Console** → **Create database**
2. Select **PostgreSQL** → Version **15**
3. Template: **Dev/Test** (to stay in free tier)
4. Settings:
   - DB instance identifier: `skyro-db`
   - Master username: `skyro_admin`
   - Master password: (generate strong, save to Secrets Manager below)
5. Instance type: `db.t3.micro` (free tier)
6. Storage: 20 GB gp3
7. Connectivity:
   - VPC: default
   - Public access: **Yes** (dev only — restrict in production using VPC peering or SSM tunnel)
   - Create security group: `skyro-rds-sg`
     - Inbound rule: TCP 5432, source = **your current IP only**
8. Additional config:
   - Initial database name: `skyro`
9. Click **Create database** (takes ~3 minutes)

### Run migration
```bash
# Set the RDS endpoint (shown in RDS console after creation)
export DATABASE_URL="postgresql://skyro_admin:<password>@<rds-endpoint>:5432/skyro"

# Run schema + seed
python db/migrate.py
```

---

## Step 2 — Amazon ElastiCache (Redis)

### Create the cache cluster
1. Open **ElastiCache Console** → **Redis clusters** → **Create**
2. Cluster mode: **Off**
3. Name: `skyro-redis`
4. Node type: `cache.t3.micro`
5. Replicas: 0 (dev); 1+ (production)
6. Subnet group: create in the same VPC as RDS
7. Security group: `skyro-redis-sg`
   - Inbound rule: TCP 6379, source = ECS security group

```bash
# Set in your ECS task environment or .env
REDIS_URL=redis://<elasticache-endpoint>:6379
```

---

## Step 3 — Amazon ECS (Fargate)

### Push Docker images to ECR
```bash
# Create ECR repos
aws ecr create-repository --repository-name skyro/orders-service
aws ecr create-repository --repository-name skyro/fleet-ai
aws ecr create-repository --repository-name skyro/drone-backend

# Login and push (repeat for each service)
aws ecr get-login-password --region ap-south-1 | \
  docker login --username AWS --password-stdin <account-id>.dkr.ecr.ap-south-1.amazonaws.com

docker build -t skyro/orders-service ./backend-orders
docker tag skyro/orders-service:latest <account-id>.dkr.ecr.ap-south-1.amazonaws.com/skyro/orders-service:latest
docker push <account-id>.dkr.ecr.ap-south-1.amazonaws.com/skyro/orders-service:latest
```

### Create ECS Cluster
1. ECS Console → **Clusters** → **Create Cluster**
2. Name: `skyro-cluster`
3. Infrastructure: **AWS Fargate**

### Create Task Definitions (one per service)
For each service (`fleet-ai`, `orders-service`, `drone-backend`):
- Launch type: **Fargate**
- CPU: 0.25 vCPU, Memory: 512 MB (dev)
- Container image: ECR URI from above
- Port mappings: 8002 / 8000 / 8080
- **Environment variables**: pulled from Secrets Manager (see Step 4)

---

## Step 4 — AWS Secrets Manager

### Store credentials (never put in code/git)
```bash
# RDS connection string
aws secretsmanager create-secret \
  --name "skyro/DATABASE_URL" \
  --secret-string "postgresql+asyncpg://skyro_admin:<pass>@<rds-endpoint>:5432/skyro"

# Redis connection string
aws secretsmanager create-secret \
  --name "skyro/REDIS_URL" \
  --secret-string "redis://<elasticache-endpoint>:6379"
```

### Wire to ECS Task Role
1. Create IAM Role `skyro-ecs-task-role`
2. Attach policy: `SecretsManagerReadWrite` (or a custom policy scoped to `skyro/*`)
3. In ECS Task Definition → **Task Role** → select `skyro-ecs-task-role`
4. ECS will inject secrets as environment variables at runtime via:
   ```json
   { "name": "DATABASE_URL", "valueFrom": "arn:aws:secretsmanager:...:skyro/DATABASE_URL" }
   ```

---

## Step 5 — Amazon SQS (Async Order Events)

### Create queue
```bash
aws sqs create-queue --queue-name skyro-order-events
```

### Wire up
- **Orders Service** publishes to SQS when order status → `CONFIRMED`
- **Fleet AI** polls SQS to trigger drone assignment automatically

> This decouples the two services — Orders doesn't need to know Fleet AI's URL.

---

## Step 6 — API Gateway + Amazon Cognito

### Cognito (auth)
1. Cognito Console → **User Pools** → **Create user pool**
2. Name: `skyro-users`
3. App client: `skyro-web`
4. Issue JWT tokens on login

### API Gateway
1. API Gateway Console → **Create API** → **HTTP API**
2. Add integrations:
   - `/api/orders/*` → Orders Service ECS (via load balancer URL)
   - `/api/fleet/*`  → Fleet AI ECS
   - `/api/drone/*`  → Drone Backend ECS
3. Add JWT Authorizer → Cognito User Pool
4. All authenticated routes protected automatically

---

## Step 7 — Amazon CloudWatch

### Drone heartbeat alarm
```bash
# Alarm if no heartbeat message logged for 60+ seconds
aws cloudwatch put-metric-alarm \
  --alarm-name "drone-heartbeat-lost" \
  --metric-name "DroneHeartbeatAge" \
  --namespace "Skyro/FleetAI" \
  --statistic Maximum \
  --period 60 \
  --threshold 60 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --evaluation-periods 1 \
  --alarm-actions <SNS-topic-ARN>
```

### Container logs
All ECS tasks auto-send logs to CloudWatch Log Groups:
- `/ecs/skyro-orders`
- `/ecs/skyro-fleet-ai`
- `/ecs/skyro-drone-backend`

---

## Step 8 — DynamoDB (Telemetry) + S3 (Archives)

### DynamoDB
```bash
aws dynamodb create-table \
  --table-name DroneTelemetryLogs \
  --attribute-definitions \
    AttributeName=drone_id,AttributeType=S \
    AttributeName=timestamp,AttributeType=N \
  --key-schema \
    AttributeName=drone_id,KeyType=HASH \
    AttributeName=timestamp,KeyType=RANGE \
  --billing-mode PAY_PER_REQUEST
```

Each drone telemetry ping → `boto3.resource('dynamodb').Table('DroneTelemetryLogs').put_item({...})`

### S3 (flight path archives)
```bash
aws s3 mb s3://skyro-flight-archives
```

Completed missions export their DynamoDB telemetry to `s3://skyro-flight-archives/<drone_id>/<mission_id>.jsonl` for long-term storage and future ML training.

---

## Production Environment Variables Summary

| Variable | Where to set | Example value |
|---|---|---|
| `DATABASE_URL` | Secrets Manager → ECS | `postgresql+asyncpg://skyro_admin:pass@rds-endpoint:5432/skyro` |
| `REDIS_URL` | Secrets Manager → ECS | `redis://elasticache-endpoint:6379` |
| `ORDERS_API_BASE` | ECS Task Env | `http://orders-alb.internal:8000` |
| `DRONE_BACKEND_URL` | ECS Task Env | `http://drone-alb.internal:8080` |
| `CORS_ORIGINS` | ECS Task Env | `https://yourdomain.com` |
| `SAFE_THRESHOLD_M` | ECS Task Env | `20` |
