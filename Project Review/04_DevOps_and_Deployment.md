# SKYRO — DevOps & Deployment Review

> Docker setup, AWS infrastructure, environment variables, startup scripts, and production deployment guide.

---

## 1. Docker Setup

### docker-compose.yml — 5 Services

```
┌──────────────────────────────────────────────────────┐
│                  docker-compose.yml                   │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ postgres │  │  redis   │  │                  │  │
│  │ :5432    │  │  :6379   │  │                  │  │
│  └────┬─────┘  └────┬─────┘  │                  │  │
│       │              │        │                  │  │
│  ┌────┴──────────────┴────┐   │                  │  │
│  │   backend-orders       │   │    backend       │  │
│  │   :8000                │   │    :8080         │  │
│  └────────────┬───────────┘   │    :14550/udp    │  │
│               │               └────────┬─────────┘  │
│  ┌────────────┴────────────────────────┴──────┐     │
│  │          backend-fleet-ai                   │     │
│  │          :8002                               │     │
│  │          depends_on: all three above         │     │
│  └─────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────┘
```

| Service | Image | Ports | Depends On |
|---------|-------|-------|------------|
| `postgres` | `postgres:15-alpine` | 5432 | — |
| `redis` | `redis:7-alpine` | 6379 | — |
| `backend` | Build `./backend` | 8080, 14550/udp | — |
| `backend-orders` | Build `./backend-orders` | 8000 | postgres, redis |
| `backend-fleet-ai` | Build `./backend-fleet-ai` | 8002 | backend, backend-orders, redis |

### Startup Order
1. **postgres** + **redis** start first (no dependencies)
2. **backend** starts (no DB dependency — is the MAVSDK hardware interface only)
3. **backend-orders** starts after postgres is healthy
4. **backend-fleet-ai** starts last (depends on all three)

### Database Auto-Initialization
```yaml
postgres:
  volumes:
    - ./db/schema.sql:/docker-entrypoint-initdb.d/01_schema.sql
    - ./db/seed.sql:/docker-entrypoint-initdb.d/02_seed.sql
```
PostgreSQL runs these SQL files automatically on first start.

### Commands
```bash
# Start all services
docker-compose up --build

# Start specific service
docker-compose up -d postgres redis

# View logs
docker-compose logs -f backend-fleet-ai

# Rebuild a single service
docker-compose build backend-orders

# Stop everything
docker-compose down

# Stop and remove volumes (reset DB)
docker-compose down -v
```

---

## 2. Dockerfiles

### backend/Dockerfile (Python 3.11)
- Base: `python:3.11-slim`
- Installs: `libglib2.0-0` (needed by MAVSDK native extensions)
- Exposes: 8080
- CMD: `uvicorn main:app --host 0.0.0.0 --port 8080 --workers 1`

### backend-orders/Dockerfile (Python 3.11)
- Base: `python:3.11-slim`
- No special build deps needed
- Exposes: 8000
- CMD: `uvicorn main:app --host 0.0.0.0 --port 8000`

### backend-fleet-ai/Dockerfile (Python 3.11)
- Base: `python:3.11-slim`
- Sets default env vars (DRONE_BACKEND_URL, ORDERS_API_BASE, etc.)
- Includes healthcheck: HTTP ping to :8002 every 10s
- Exposes: 8002
- CMD: `uvicorn main:app --host 0.0.0.0 --port 8002 --log-level info`

---

## 3. Local Development (Without Docker)

### PowerShell Startup (`start-all.ps1`)

```powershell
.\start-all.ps1
# Opens 3 PowerShell windows:
#   Window 1: backend-orders on port 8000 (green)
#   Window 2: backend (drone) on port 8080 (yellow)
#   Window 3: backend-fleet-ai on port 8002 (magenta)
```

The script:
1. Auto-detects Python venv (`dronw\Scripts\python.exe` or `dron\Scripts\python.exe`)
2. Sets `DATABASE_URL` to AWS RDS for orders and fleet-ai
3. Sets `ORDERS_API_BASE`, `DRONE_BACKEND_URL`, `DRONE_BACKEND_WS` for fleet-ai
4. Starts each with `uvicorn main:app --host 0.0.0.0 --port XXXX --reload`

### Frontend
```bash
cd frontend
npm install
npm run dev:user    # Port 5173
npm run dev:vendor  # Port 5174
npm run dev:admin   # Port 5175
```

---

## 4. Complete Environment Variables

### Frontend (.env files)

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `VITE_API_BASE` | Yes | Orders backend URL | `http://localhost:8000` |
| `VITE_DRONE_API_BASE` | Yes | Drone backend URL | `http://localhost:8080` |
| `VITE_VARIANT` | Yes | App mode | `user` / `vendor` / `admin` |
| `VITE_DEMO_MODE` | No | Skip real payments | `true` |
| `VITE_MAPBOX_TOKEN` | No | Mapbox satellite map | `pk.eyJ1...` |
| `GEMINI_API_KEY` | No | Google Gemini AI | `AIza...` |

### backend-orders

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `DATABASE_URL` | Yes | DB connection string | `postgresql+asyncpg://...` |
| `PORT` | No | Server port | `8000` |
| `HOST` | No | Bind address | `0.0.0.0` |
| `CORS_ORIGINS` | No | Allowed origins | `*` or `https://skyro.app` |
| `COGNITO_USER_POOL_ID` | For auth | Cognito pool | `ap-south-1_xxxxxxx` |
| `COGNITO_CLIENT_ID` | For auth | Cognito app client | `1abc2def3ghi...` |
| `AWS_REGION` | For auth | AWS region | `ap-south-1` |
| `RAZORPAY_KEY_ID` | For payments | Razorpay API key | `rzp_test_...` |
| `RAZORPAY_KEY_SECRET` | For payments | Razorpay secret | `abc123...` |

### backend (Drone)

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `HOST` | No | Bind address | `0.0.0.0` |
| `PORT` | No | Server port | `8080` |
| `FLEET_AI_URL` | No | Fleet AI URL | `http://localhost:8002` |
| `ORDERS_API_BASE` | No | Orders URL | `http://localhost:8000` |

### backend-fleet-ai

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `DRONE_BACKEND_URL` | Yes | Drone HTTP URL | `http://localhost:8080` |
| `DRONE_BACKEND_WS` | Yes | Drone WebSocket URL | `ws://localhost:8080/ws` |
| `ORDERS_API_BASE` | Yes | Orders URL | `http://localhost:8000` |
| `DATABASE_URL` | No | Direct DB access | `postgresql+asyncpg://...` |
| `REDIS_URL` | No | Redis URL | `redis://localhost:6379` |
| `CORS_ORIGINS` | No | Allowed origins | `*` |
| `SAFE_THRESHOLD_M` | No | Conflict distance | `20` (metres) |
| `PREDICT_SECONDS` | No | Conflict lookahead | `7` (seconds) |
| `CRUISE_SPEED_MPS` | No | Drone speed for ETA | `5.0` (m/s) |
| `ZONE_MAX_WAIT_SECONDS` | No | Stale reservation timeout | `300` (seconds) |

---

## 5. AWS Production Infrastructure

### Services Used

| AWS Service | Resource | Purpose |
|------------|----------|---------|
| **RDS** | `skyro-db` (PostgreSQL 15, db.t3.micro) | Primary database |
| **ElastiCache** | `skyro-redis` (Redis 7, cache.t3.micro) | Fleet state caching |
| **ECS Fargate** | `skyro-cluster` (3 task definitions) | Container hosting |
| **ECR** | 3 repos (orders, fleet-ai, drone) | Docker image registry |
| **Cognito** | `skyro-users` pool, `skyro-web` client | User authentication |
| **Secrets Manager** | `skyro/DATABASE_URL`, `skyro/REDIS_URL` | Credential storage |
| **API Gateway** | HTTP API with JWT authorizer | Routing + auth |
| **CloudWatch** | Log groups + heartbeat alarm | Monitoring |
| **DynamoDB** | `DroneTelemetryLogs` table | Telemetry storage |
| **S3** | `skyro-flight-archives` bucket | Flight path archives |
| **SQS** | `skyro-order-events` queue | Async event decoupling |

### AWS Setup Steps (Summary)
1. **RDS:** Create PostgreSQL 15 instance → Run `python db/migrate.py`
2. **ElastiCache:** Create Redis cluster in same VPC
3. **ECR:** Create 3 repos → `docker build` + `docker push`
4. **ECS:** Create Fargate cluster → Define 3 task definitions → Create services
5. **Secrets Manager:** Store DATABASE_URL and REDIS_URL
6. **Cognito:** Create user pool + app client → Configure JWT
7. **API Gateway:** Create HTTP API with routes to ECS ALBs
8. **CloudWatch:** Drone heartbeat alarm → SNS notification

### Security Groups
- `skyro-rds-sg`: TCP 5432 from ECS security group only
- `skyro-redis-sg`: TCP 6379 from ECS security group only
- ECS tasks: outbound all, inbound from API Gateway ALB

---

## 6. Production Deployment Checklist

```
□  AWS RDS PostgreSQL created and accessible
□  Schema and seed data migrated (python db/migrate.py)
□  ElastiCache Redis cluster running
□  ECR repos created, images pushed
□  ECS Fargate cluster + services running
□  Secrets Manager storing DATABASE_URL, REDIS_URL
□  Cognito user pool configured
□  API Gateway routing to ECS services
□  CloudWatch alarms configured
□  Frontend built and deployed (Vercel / S3+CloudFront / etc.)
□  CORS_ORIGINS set to production domain
□  SSL/TLS configured on all endpoints
□  Environment variables verified in all ECS task definitions
```

---

## 7. Monitoring & Logging

### CloudWatch Log Groups
- `/ecs/skyro-orders` — Orders service logs
- `/ecs/skyro-fleet-ai` — Fleet AI logs
- `/ecs/skyro-drone-backend` — Drone backend logs

### Drone Heartbeat Alarm
```bash
# Triggers if no heartbeat for 60+ seconds
aws cloudwatch put-metric-alarm \
  --alarm-name "drone-heartbeat-lost" \
  --metric-name "DroneHeartbeatAge" \
  --namespace "Skyro/FleetAI" \
  --threshold 60 \
  --comparison-operator GreaterThanOrEqualToThreshold
```

### Telemetry Archival
- **DynamoDB:** Each drone telemetry ping → `DroneTelemetryLogs` table (drone_id + timestamp)
- **S3:** Completed missions → `s3://skyro-flight-archives/<drone_id>/<mission_id>.jsonl`

---

## 8. Android Client Local Development (Skyro_app)

The native Android app can be run and debugged locally using Android Studio.

### Prerequisites
- **Android Studio** (Koala or newer recommended)
- Android SDK 34 (Android 14) or newer
- **Google Play Services** (configured on the target emulator or physical device for Google Maps)

### Configuration Setup
1. **Gemini API Key**: Create a `.env` file in the `Skyro_app/` directory and configure the environment variable:
   ```env
   GEMINI_API_KEY=AIzaSy... # Your Google Gemini API Key
   ```
2. **ngrok Tunnel Configuration**:
   - Start ngrok forwarding for backend-orders (port 8000) and backend-drone (port 8080).
   - In [NetworkConfig.kt](file:///c:/Users/SRMAP/Documents/Skyworks/Skyro/Skyro_app/app/src/main/java/com/example/data/NetworkConfig.kt), update `DEFAULT_BASE_URL` and `DEFAULT_DRONE_BASE_URL` with your temporary ngrok URLs:
     ```kotlin
     const val DEFAULT_BASE_URL = "https://your-orders-subdomain.ngrok-free.app"
     const val DEFAULT_DRONE_BASE_URL = "https://your-drone-subdomain.ngrok-free.app"
     ```
   - Alternatively, override the API URL directly in the app UI via **Profile → API Settings**.

### Running the App
1. Open Android Studio and choose **Open** on the [Skyro_app](file:///c:/Users/SRMAP/Documents/Skyworks/Skyro/Skyro_app) directory.
2. Allow Gradle sync to complete.
3. If using local build configurations, remove the custom signing configuration from the app's `build.gradle.kts` if compiling a vanilla debug build:
   - Line to remove: `signingConfig = signingConfigs.getByName("debugConfig")`
4. Select your target physical device or emulator and press **Run**.

---

*Document generated: June 2026 | Project: Skyro Drone Delivery System | Campus: SRM University, Amaravati*
