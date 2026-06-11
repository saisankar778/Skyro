# SKYRO — Project Overview

> **Skyro** is an autonomous drone-based food delivery system built for SRM University, Amaravati campus. Students order food from on-campus restaurants through a mobile-friendly web app, and real ArduPilot/Pixhawk drones deliver it to designated campus blocks — fully automated from takeoff to landing.

---

## What is Skyro?

Skyro is a complete end-to-end system consisting of:

- **A food ordering web app** (like Swiggy/Zomato) where students browse restaurants, add items to cart, pay, and track their order in real-time on a live map
- **A native Android mobile application** built in Kotlin with Jetpack Compose, utilizing a local Room database for offline caching, Google Maps for tracking, and Retrofit/WebSockets for server synchronization
- **A drone control backend** that connects to real ArduPilot drones via MAVLink protocol and autonomously flies them to delivery locations
- **An AI fleet management layer** that intelligently assigns drones, prevents mid-air collisions, and manages landing pad reservations
- **A cloud database** on AWS RDS (PostgreSQL) storing all orders, restaurants, menus, users, drone data, and delivery missions

---

## System Architecture (Bird's Eye View)

```
  ┌────────────────────────────────────────────────────────────────────────┐
  │                           CLIENT APPLICATIONS                          │
  │                                                                        │
  │   User Web (:5173)     Android App (Native)     Admin Web (:5175)      │
  │   • Browse food        • Browse food (Room)     • Fleet dashboard      │
  │   • Place orders       • Add to cart / checkout • Connect drones       │
  │   • Razorpay pay       • Google Maps tracking   • Launch missions      │
  │   • Track drone (Map)  • WebSocket syncing      • Live map view        │
  │                                                                        │
  │   Vendor Web (:5174): See incoming orders & update cooking status      │
  └───────┬───────────────────────┬──────────────────────┬─────────────────┘
          │                       │                      │
          │ REST + WebSocket      │ REST + WebSocket      │ REST + WS
          ▼                       ▼                      ▼
  ┌───────────────┐    ┌──────────────────┐    ┌────────────────────┐
  │ ORDERS SERVICE│    │  DRONE BACKEND   │    │   FLEET AI         │
  │ Port 8000     │    │  Port 8080       │    │   Port 8002        │
  │               │    │                  │    │                    │
  │ • Orders CRUD │◄───│ • MAVSDK conn    │◄───│ • AI scoring       │
  │ • Restaurants │    │ • MAVLink control│    │ • Conflict detect  │
  │ • Menu items  │    │ • Arm/Takeoff    │    │ • Landing zones    │
  │ • Auth/Login  │    │ • Navigate GPS   │    │ • Home pad mgmt   │
  │ • Payments    │    │ • Land & Servo   │    │ • Mission auth     │
  │ • Locations   │    │ • Return home    │    │ • Telemetry sync   │
  └───────┬───────┘    └──────────────────┘    └────────┬───────────┘
          │                                             │
          ▼                                             ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │           PostgreSQL (AWS RDS)  +  Redis (ElastiCache)          │
  │                                                                  │
  │   Database: skyro  |  User: skyro_admin  |  Region: ap-south-1  │
  │   11 tables: locations, users, restaurants, menu_items, orders,  │
  │   order_items, drones, delivery_missions, home_location_         │
  │   reservations, system_events                                    │
  └──────────────────────────────────────────────────────────────────┘
```

---

## The Delivery Flow (How Everything Connects)

```
Step 1:  Student opens Skyro User app on phone/browser
Step 2:  Browses restaurants → selects items → adds to cart
Step 3:  Chooses delivery block (SR Block, C Block, Admin Block, etc.)
Step 4:  Pays via Razorpay (or demo mode) → Order placed

                    ↓ REST POST to backend-orders

Step 5:  Order saved to PostgreSQL, WebSocket broadcasts to all clients
Step 6:  Vendor app shows new order notification
Step 7:  Vendor accepts → starts cooking → marks "Ready for Launch"

                    ↓ WebSocket broadcast to Admin app

Step 8:  Admin sees order is ready → clicks "Launch Drone"
Step 9:  Frontend calls drone backend POST /api/launch with:
         { droneId, connectionString, block, orderId }

                    ↓ Drone backend processes

Step 10: MAVSDK-Python connects to real drone via System.connect()
Step 11: Arms motors → Takes off to 20m altitude
Step 12: Navigates to delivery block GPS coordinates at 5 m/s
Step 13: Lands at destination → Disarms
Step 14: Actuates payload release servo (actuator index 1) to release food payload
Step 15: Waits 5 seconds for payload to clear

                    ↓ REST call to Fleet AI

Step 16: Requests home pad from Fleet AI (/reserve-home-location)
Step 17: Fleet AI finds a free home pad → reserves it → returns GPS

                    ↓ Drone backend continues

Step 18: Re-arms → Takes off → Flies to assigned home pad
Step 19: Lands at home → Disarms → Releases home pad reservation

                    ↓ REST PATCH to backend-orders

Step 20: Marks order as "Delivered" in database
Step 21: WebSocket broadcasts delivery notification
Step 22: Student gets "Your order has been delivered!" notification
```

---

## Technology Stack

| Layer | Technologies |
|-------|-------------|
| **Frontend (Web)** | React 19, TypeScript, Vite 6, TailwindCSS 3, Framer Motion, Leaflet, Mapbox GL, PWA |
| **Mobile App (Android)** | Kotlin, Jetpack Compose, Room SQLite DB, Retrofit 2, Moshi, OkHttp 3, Google Maps SDK |
| **Backend (Drone)** | Python 3.11, FastAPI, MAVSDK-Python, pymavlink, SQLAlchemy |
| **Backend (Orders)** | Python 3.11, FastAPI, SQLAlchemy, asyncpg, boto3, Razorpay SDK |
| **Backend (Fleet AI)** | Python 3.11, FastAPI, httpx, websockets, asyncpg, Redis |
| **Database** | PostgreSQL 15 (AWS RDS), Redis 7 (ElastiCache) |
| **Auth** | AWS Cognito (OTP + Email/Password) |
| **Payments** | Razorpay (INR) |
| **Containerization** | Docker, Docker Compose |
| **Cloud** | AWS (RDS, ElastiCache, ECS Fargate, ECR, Cognito, API Gateway, CloudWatch, S3, DynamoDB, SQS) |
| **Drone Hardware** | ArduPilot/Pixhawk, MAVLink protocol, Servo payload mechanism |

---

## Project File Structure (Complete)

```
Skyro/
├── Skyro_app/                     # Native Android Kotlin Application
│   ├── app/src/main/java/com/example/
│   │   ├── MainActivity.kt        # Entry Point & Screen Router
│   │   ├── data/                  # Room DB, Retrofit Client, Repositories
│   │   └── ui/                    # ViewModels, Screens, Theme, Components
│   ├── build.gradle.kts           # Gradle dependencies & properties
│   └── README.md
│
├── frontend/                      # React + Vite + TypeScript (Web App)
│   ├── src/
│   │   ├── App.tsx                # Root — routes to User/Vendor/Admin view
│   │   ├── types.ts               # TypeScript interfaces & enums
│   │   ├── constants.ts           # GPS coords, restaurants, menus, drones
│   │   ├── context/AppContext.tsx  # Central state + API calls + WebSocket
│   │   ├── hooks/useAppData.ts    # Data fetching hooks
│   │   ├── utils/loadScript.ts    # Dynamic script loader
│   │   └── components/            # All UI components (see Frontend Review)
│   ├── .env.user / .env.vendor / .env.admin
│   ├── vite.config.ts             # Multi-variant build + PWA config
│   ├── package.json               # npm dependencies
│   └── tailwind.config.cjs
│
├── backend/                       # Drone Control Service (Port 8080)
│   ├── main.py                    # FastAPI app + MAVSDK drone control registry
│   ├── drone_agent.py             # MAVSDKDroneAgent (telemetry streams + connection semaphore)
│   ├── mission_executor.py        # MissionExecutor (isolated async task-based delivery flow)
│   ├── drone_registry.py          # DroneRegistry (multiple drone lifecycle manager)
│   ├── ws_manager.py              # WebSocketManager (real-time telemetry broadcaster)
│   ├── models.py                  # Pydantic models & DroneState data schemas
│   ├── requirements.txt           # mavsdk, pymavlink, fastapi, uvicorn, etc.
│   └── Dockerfile                 # Python 3.11 + MAVSDK runtime
│
├── backend-orders/                # Orders & Data Service (Port 8000)
│   ├── main.py                    # FastAPI route registrations
│   ├── database.py                # DB connection (Postgres/SQLite dual)
│   ├── crud.py                    # CRUD operations + status mapping
│   ├── schemas.py                 # Pydantic models
│   ├── auth.py                    # AWS Cognito auth
│   ├── payments.py                # Razorpay integration
│   ├── events.py                  # WebSocket broadcasting
│   ├── requirements.txt
│   └── Dockerfile
│
├── backend-fleet-ai/              # Fleet Intelligence (Port 8002)
│   ├── main.py                    # FastAPI + WS manager + startup hooks
│   ├── scheduler.py               # AI drone scoring engine
│   ├── state_manager.py           # Real-time drone state via WS
│   ├── landing.py                 # Landing zone + home pad reservations
│   ├── traffic.py                 # Air traffic conflict detection
│   ├── authorization.py           # Mission safety gate
│   ├── models.py                  # Pydantic models
│   ├── requirements.txt
│   └── Dockerfile
│
├── db/                            # Database Management
│   ├── schema.sql                 # Full PostgreSQL schema (11 tables)
│   ├── seed.sql                   # Production seed data
│   └── migrate.py                 # Migration script for AWS RDS
│
├── infrastructure/
│   └── aws-setup.md               # AWS provisioning guide
│
├── docker-compose.yml             # All 5 services
├── start-all.ps1                  # Start backends locally (Windows)
├── start-local.ps1                # Simplified local start
└── Project Review.md              # Single-file project review
```

---

## How to Run the Project

### Option A: Docker (Recommended)
```bash
docker-compose up --build
# Starts: postgres(:5432) + redis(:6379) + backend(:8080) + orders(:8000) + fleet-ai(:8002)
```

### Option B: Local Development
```powershell
# Terminal 1 — Start all backends
.\start-all.ps1

# Terminal 2 — Start frontend (pick one)
cd frontend
npm run dev:user    # User app on http://localhost:5173
npm run dev:vendor  # Vendor app on http://localhost:5174
npm run dev:admin   # Admin app on http://localhost:5175
```

### Option C: AWS Production
Follow `infrastructure/aws-setup.md` to provision RDS, ElastiCache, ECS, Cognito, etc.

---

## Related Review Documents

| File | Contents |
|------|----------|
| [01_Frontend_Review.md](./01_Frontend_Review.md) | Complete frontend architecture, components, state management, screens |
| [02_Backend_Review.md](./02_Backend_Review.md) | All three backend services, API endpoints, drone control logic |
| [03_Database_Review.md](./03_Database_Review.md) | Schema, tables, enums, seed data, migration, connection setup |
| [04_DevOps_and_Deployment.md](./04_DevOps_and_Deployment.md) | Docker, AWS infrastructure, environment variables, startup scripts |
| [05_Mobile_App_Review.md](./05_Mobile_App_Review.md) | Native Android mobile app (Kotlin/Compose), SQLite caching, telemetry |

---

*Document generated: May 2026 | Project: Skyro Drone Delivery System | Campus: SRM University, Amaravati*
