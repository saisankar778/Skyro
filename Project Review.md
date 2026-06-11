# SKYRO — Complete Project Review

> **Skyro** is an autonomous drone food delivery system built for SRM University, Amaravati. Users order food from on-campus restaurants via a mobile-friendly web app, and real drones (ArduPilot/Pixhawk) deliver it to designated campus blocks.

---

## 1. High-Level Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                          CLIENT APPLICATIONS                           │
│  • React Web variants: User (:5173) | Vendor (:5174) | Admin (:5175)   │
│  • Native Android App (Kotlin + Compose)                               │
│  Communicates via REST + WebSocket to backends                         │
└──────────┬─────────────────────┬────────────────────┬──────────────────┘
           │ REST/WS             │ REST/WS             │ REST/WS
           ▼                     ▼                     ▼
┌─────────────────┐   ┌──────────────────┐   ┌──────────────────────┐
│ backend-orders  │   │ backend (Drone)  │   │ backend-fleet-ai     │
│ Port 8000       │   │ Port 8080        │   │ Port 8002            │
│ FastAPI+Python  │   │ FastAPI+MAVSDK   │   │ FastAPI+Python       │
│                 │◄──┤                  │◄──┤                      │
│ Orders, Auth,   │   │ MAVLink control, │   │ AI scheduling,       │
│ Restaurants,    │   │ Arm/Takeoff/Nav, │   │ Traffic deconfliction│
│ Menus, Payments │   │ Servo payload,   │   │ Landing zones,       │
│                 │   │ Return-to-home   │   │ Home reservations    │
└────────┬────────┘   └──────────────────┘   └──────────┬───────────┘
         │                                              │
         ▼                                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│              PostgreSQL (AWS RDS) + Redis (ElastiCache)              │
│  Database: skyro | User: skyro_admin | Region: ap-south-1            │
└──────────────────────────────────────────────────────────────────────┘
```

**Data Flow for a delivery:**
1. **User** opens Web app or Android app → browses restaurants → adds items to cart → places order
2. **backend-orders** saves order to PostgreSQL, broadcasts via WebSocket
3. **Vendor** sees new order in VendorView → accepts → marks "Cooking" → marks "Ready for Launch"
4. **Admin** clicks "Launch Drone" in AdminView → frontend calls `backend:8080/api/launch`
5. **backend (Drone)** connects to real drone via MAVSDK-Python → arms → takes off → flies to block → lands → drops payload via servo → re-arms → requests home pad from Fleet AI → flies home → lands
6. On delivery, backend notifies **backend-orders** to mark order "Delivered"
7. All Web and Android clients get real-time updates via WebSocket

---

## 2. Project File Structure

```
Skyro/
├── Skyro_app/                 # Native Android Kotlin Application (Jetpack Compose)
│   ├── app/src/main/java/com/example/
│   │   ├── MainActivity.kt    # Screen Router & Theme setup
│   │   ├── data/              # SQLite Room DB, Retrofit Client, Repositories
│   │   └── ui/                # ViewModels, Screens, Theme, Components
│   └── build.gradle.kts
│
├── frontend/                  # React + Vite + TypeScript + TailwindCSS (Web Client)
│   ├── src/
│   │   ├── App.tsx            # Root component - routes to User/Vendor/Admin
│   │   ├── types.ts           # TypeScript interfaces & enums
│   │   ├── constants.ts       # GPS coords, restaurants, menu items, drones
│   │   ├── context/
│   │   │   └── AppContext.tsx  # Central state: orders, drones, WS connections
│   │   ├── hooks/
│   │   │   └── useAppData.ts  # Fetches restaurants/menus/locations from API
│   │   ├── utils/
│   │   │   └── loadScript.ts  # Dynamic script loader (Razorpay)
│   │   └── components/
│   │       ├── UserView.tsx        # User-facing food ordering UI
│   │       ├── VendorView.tsx      # Restaurant dashboard
│   │       ├── AdminView.tsx       # Fleet management dashboard
│   │       ├── Map.tsx             # Leaflet/Mapbox live drone map
│   │       ├── Header.tsx          # App header
│   │       └── user/              # User sub-screens
│   │           ├── HomeScreen.tsx       # Landing page with restaurants
│   │           ├── RestaurantDetail.tsx # Menu browsing
│   │           ├── CartDrawer.tsx       # Shopping cart
│   │           ├── PaymentScreen.tsx    # Razorpay checkout
│   │           ├── OrdersScreen.tsx     # Order history
│   │           ├── TrackingScreen.tsx   # Live drone tracking map
│   │           ├── LoginScreen.tsx      # AWS Cognito login
│   │           ├── SignupScreen.tsx     # Registration
│   │           ├── ProfileScreen.tsx    # User profile
│   │           ├── BlockScreen.tsx      # Delivery location picker
│   │           └── DeliveryMap.tsx      # Delivery route visualization
│   ├── .env.user              # VITE_VARIANT=user, port 5173
│   ├── .env.vendor            # VITE_VARIANT=vendor, port 5174
│   ├── .env.admin             # VITE_VARIANT=admin, port 5175
│   ├── vite.config.ts         # Multi-variant build config + PWA
│   ├── package.json           # Dependencies
│   └── tailwind.config.cjs    # Tailwind configuration
│
├── backend/                   # Drone Control Backend (Port 8080)
│   ├── main.py                # FastAPI app + MAVSDK drone control registry
│   ├── drone_agent.py         # MAVSDKDroneAgent (telemetry streams + connection semaphore)
│   ├── mission_executor.py    # MissionExecutor (isolated async task-based delivery flow)
│   ├── drone_registry.py      # DroneRegistry (multiple drone lifecycle manager)
│   ├── ws_manager.py          # WebSocketManager (real-time telemetry broadcaster)
│   ├── models.py              # Pydantic models & DroneState data schemas
│   ├── requirements.txt       # mavsdk, pymavlink, fastapi, uvicorn, etc.
│   └── Dockerfile             # Python 3.11 + MAVSDK runtime
│
├── backend-orders/            # Orders & Data Backend (Port 8000)
│   ├── main.py                # FastAPI app with all route registrations
│   ├── database.py            # DB connection (PostgreSQL via asyncpg / SQLite fallback)
│   ├── crud.py                # All CRUD operations with status mapping
│   ├── schemas.py             # Pydantic models for API request/response
│   ├── auth.py                # AWS Cognito authentication (OTP + email)
│   ├── payments.py            # Razorpay payment integration
│   ├── events.py              # WebSocket broadcast for real-time updates
│   ├── requirements.txt       # fastapi, asyncpg, boto3, razorpay, etc.
│   └── Dockerfile             # Python 3.11
│
├── backend-fleet-ai/          # Fleet Intelligence Backend (Port 8002)
│   ├── main.py                # FastAPI app, WS manager, startup hooks
│   ├── scheduler.py           # AI scoring engine for drone assignment
│   ├── state_manager.py       # Real-time drone state via WS subscription
│   ├── landing.py             # Delivery zone + home pad reservation system
│   ├── traffic.py             # Air traffic conflict detection
│   ├── authorization.py       # Mission safety gate (4-check authorization)
│   ├── models.py              # All Pydantic models for Fleet AI
│   ├── requirements.txt       # fastapi, httpx, websockets, asyncpg, redis
│   └── Dockerfile             # Python 3.11
│
├── db/                        # Database Schema & Migration
│   ├── schema.sql             # Full PostgreSQL schema (11 tables)
│   ├── seed.sql               # Seed data (restaurants, menus, locations)
│   └── migrate.py             # Migration script for AWS RDS
│
├── infrastructure/
│   └── aws-setup.md           # AWS provisioning guide
│
├── docker-compose.yml         # All 5 services (3 backends + postgres + redis)
├── start-all.ps1              # PowerShell script to start all backends locally
└── start-local.ps1            # Simplified local startup
```

---

## 3. The Three Backend Services

### 3.1 backend-orders (Port 8000) — Orders & Data Service

**Role:** Central data service. Manages orders, restaurants, menus, locations, users, authentication, and payments.

**Tech:** FastAPI, SQLAlchemy, asyncpg (PostgreSQL) / aiosqlite (SQLite fallback)

**Key API Endpoints:**
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/orders` | Create a new food order |
| GET | `/api/orders` | List all orders |
| GET | `/api/orders/{id}` | Get single order |
| PATCH | `/api/orders/{id}` | Update order status |
| POST | `/api/orders/{id}/assign-drone` | Fleet AI atomic drone lock |
| GET | `/api/restaurants` | List restaurants (from DB) |
| GET | `/api/menu-items` | Menu items (filterable by restaurant) |
| GET | `/api/locations` | GPS locations (HOME/RESTAURANT/DELIVERY_BLOCK) |
| POST | `/api/auth/signup` | Cognito user registration |
| POST | `/api/auth/start` | OTP login initiation |
| POST | `/api/auth/verify` | OTP verification |
| POST | `/api/auth/email/signup` | Email registration |
| POST | `/api/auth/email/login` | Email/password login |
| POST | `/api/payments/razorpay/order` | Create Razorpay payment |
| POST | `/api/payments/razorpay/verify` | Verify payment signature |
| WS | `/ws` | Real-time order event broadcast |

**Status Mapping:** The CRUD layer translates between frontend-friendly statuses (`Placed`, `Accepted`, `Cooking`, `Ready for Launch`, `En Route`, `Delivered`) and PostgreSQL enum values (`CREATED`, `CONFIRMED`, `PREPARING`, `READY_FOR_PICKUP`, `IN_FLIGHT`, `DELIVERED`).

**Database Connection:** `database.py` auto-detects PostgreSQL vs SQLite from `DATABASE_URL`. For PostgreSQL, it uses a custom `_AsyncPGDatabase` wrapper around `asyncpg` that mimics the `databases` library API and handles SQL compilation from SQLAlchemy to asyncpg's `$1, $2` positional params.

---

### 3.2 backend (Port 8080) — Drone Control Service

**Role:** Direct hardware interface. Connects to real ArduPilot drones via MAVSDK-Python, controls arming, takeoff, navigation, landing, servo payload release, and return-to-home.

**Tech:** FastAPI, MAVSDK-Python, pymavlink, SQLAlchemy (local SQLite for mission logs)

**Key API Endpoints:**
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/launch` | Start full delivery mission |
| POST | `/api/connect` | Connect to a drone |
| POST | `/api/status` | Get single drone status |
| GET | `/api/drones` | List connected drones |
| GET | `/api/drones/status` | Full telemetry (used by Fleet AI) |
| GET | `/api/drones/{id}/status` | Single drone telemetry |
| POST | `/api/obstacle-alert` | Obstacle detection hook |
| POST | `/api/landing/confirm` | Landing confirmation (GPS/VISION) |
| DELETE | `/api/drones/{id}` | Disconnect drone |
| WS | `/ws` | Real-time telemetry broadcast (every 2s) |

**Mission Flow (MAVSDKDroneAgent & MissionExecutor):**
1. **Takeoff:** `arm_and_takeoff()` arms motors (retries up to 3 times) and climbs to `TAKEOFF_ALTITUDE_M` (20m).
2. **Fly to Block:** `goto_location()` navigates to the delivery block GPS coordinates using MAVSDK's 3D goto commands, limiting horizontal speed to 5 m/s.
3. **Land:** `land_and_wait()` sets the drone mode to LAND at destination block and awaits touchdown.
4. **Drop Payload:** `release_payload()` actuates the food release servo (sets actuator index 1 to 1.0 for 2s, then returns to -1.0).
5. **Reserve Home Pad:** Requests home pad from Fleet AI (`/reserve-home-location`) to receive a safe home coordinate.
6. **Return Flight:** Arms, takes off to 20m, flies to the assigned home pad GPS, and lands.
7. **Release Reservation:** Calls Fleet AI (`/release-home-location`) to unlock the landing pad for other drones.

**Connection:** Supports MAVSDK system address strings (e.g. `udp://127.0.0.1:14550`, `tcp://127.0.0.1:5760`, serial ports). Guarded by a shared connection semaphore to limit resource consumption.

**Campus Coordinates (GPS):**
| Location | Latitude | Longitude |
|----------|----------|-----------|
| SR Block | 16.462635 | 80.506472 |
| C Block | 16.461647 | 80.505693 |
| Admin Block | 16.464875 | 80.507919 |
| Yamuna Hostel | 16.466254 | 80.507579 |
| V & G Hostels | 16.463887 | 80.506658 |
| HOME_1 (default) | 16.462795 | 80.507355 |

---

### 3.3 backend-fleet-ai (Port 8002) — Fleet Intelligence Service

**Role:** AI brain of the system. Handles drone assignment, air traffic safety, landing zone management, and mission authorization.

**Tech:** FastAPI, httpx, websockets, asyncpg, redis

**Key API Endpoints:**
| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/assign-drone` | AI-based best drone selection |
| POST | `/authorize-mission` | 4-check safety gate |
| POST | `/reserve-landing` | Lock delivery zone |
| POST | `/landing/confirm` | Release delivery zone |
| GET | `/zone-status` | Delivery zone occupancy |
| POST | `/reserve-home-location` | Reserve home pad for returning drone |
| POST | `/release-home-location` | Release home pad |
| GET | `/home-status` | All 5 home pad statuses |
| GET | `/conflicts` | Predicted air traffic conflicts |
| POST | `/obstacle-alert` | Obstacle detection hook |
| GET | `/fleet-status` | Full fleet snapshot |
| WS | `/ws` | Real-time fleet push (every 2s) |

**AI Drone Scoring Formula:**
```
score = 0.40 × battery_normalized
      + 0.30 × (1 / (1 + distance_km))
      + 0.20 × availability_flag
      + 0.10 × historical_efficiency
```
Drones with battery < 15% or distance > 5km are excluded. The scorer is swappable for ML models via `scheduler.swap_scorer()`.

**Mission Authorization (4 Safety Checks):**
1. Drone must be IDLE with battery ≥ 15%
2. Order must exist and be assigned to this drone
3. Landing zone must be free
4. No predicted air traffic conflicts

Returns: `APPROVED` | `WAIT` (temporary, retry) | `DENIED` (hard failure)

**Air Traffic Conflict Detection:**
- Predicts each drone's position 7 seconds ahead using velocity vectors
- Computes pairwise 3D distances (haversine horizontal + vertical)
- Flags pairs within 20m as conflicts
- Suggests resolution: altitude separation or delayed launch
- O(n²) complexity, handles 50-100 drones in < 1ms

**State Manager:** Subscribes to drone backend's WebSocket for live telemetry. Reconnects with exponential backoff (2s → 30s). Marks drones OFFLINE after 15s of no data.

---

## 4. Frontend & Mobile Clients

### 4.1 Web Frontend Architecture

**Tech:** React 19, TypeScript, Vite, TailwindCSS, React Router, Leaflet/Mapbox, Framer Motion, PWA (vite-plugin-pwa)

### 4.2 Three Web App Variants (same codebase, different .env)

| Variant | Port | VITE_VARIANT | Purpose |
|---------|------|-------------|---------|
| User | 5173 | `user` | Food ordering, tracking, payments |
| Vendor | 5174 | `vendor` | Restaurant order management |
| Admin | 5175 | `admin` | Fleet management, drone control, map |

**How it works:** `vite.config.ts` reads `VITE_VARIANT` from the mode-specific `.env` file. `App.tsx` checks this to render the correct view (`UserView`, `VendorView`, or `AdminView`).

### 4.3 AppContext (Central State Manager)

`AppContext.tsx` is the brain of the frontend:
- Loads orders from `backend-orders` API on startup
- Subscribes to **two WebSockets**: orders WS (`:8000/ws`) and drone WS (`:8080/ws`)
- Polls drone status every 2 seconds via HTTP
- Manages: orders[], drones[], restaurants[], menuItems[], deliveryLocations[]
- Functions: `placeOrder()`, `updateOrderStatus()`, `launchDroneForOrder()`, `connectToDrone()`, `disconnectFromDrone()`, `commandRtl()`

### Key User Screens
- **HomeScreen** — Restaurant catalogue with ratings, offers, delivery times
- **RestaurantDetail** — Menu browsing with cart functionality
- **CartDrawer** — Sliding cart with item management
- **PaymentScreen** — Razorpay checkout integration
- **TrackingScreen** — Live Mapbox map showing drone position, path, ETA
- **LoginScreen/SignupScreen** — AWS Cognito authentication
- **OrdersScreen** — Order history with status colors

### Data Fetching (`useAppData.ts`)
The `useRestaurants()`, `useMenuItems()`, and `useDeliveryLocations()` hooks fetch data from the orders API (`VITE_API_BASE`). If the API is unreachable, the app falls back to hardcoded constants in `constants.ts`.

### 4.4 Android Mobile Client

**Tech:** Kotlin, Jetpack Compose, Room SQLite Database, Retrofit 2, Moshi JSON Parser, OkHttp 3 (WebSockets), Google Maps SDK

**Description:** A native Android implementation for the client ordering app. It replicates the core ordering features of the user web frontend, offering:
- **Offline Caching**: Leverages Room SQLite to cache canteens, cart state, and order history persistently.
- **WebSocket Synchronization**: Subscribes to `:8000/ws` for order state changes and `:8080/ws` for real-time drone telemetry plotting.
- **Custom headers**: Injects `ngrok-skip-browser-warning = true` header to bypass browser screens when calling local tunnel APIs.
- **Live Google Map**: Draws the delivery route, canteen, and drone location markers with speed and heading attributes.

---

## 5. Database Setup

### PostgreSQL Schema (11 Tables)

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  locations   │◄────│ restaurants  │     │    users     │
│  (GPS data)  │     │  (7 shops)   │     │              │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                    │
       │              ┌─────┴──────┐             │
       │              │ menu_items │             │
       │              │ (35 items) │             │
       │              └────────────┘             │
       │                                         │
  ┌────┴─────────────────────────────────────────┴──┐
  │                    orders                       │
  │  (pickup_location, drop_location, user, rest)   │
  └──────────┬──────────────────────────────────────┘
             │
     ┌───────┴────────┐     ┌───────────────────┐
     │  order_items   │     │      drones       │
     └────────────────┘     └───────┬───────────┘
                                    │
                          ┌─────────┴──────────┐
                          │ delivery_missions  │
                          └────────────────────┘

  + home_location_reservations (5 home pads)
  + system_events (audit log)
```

**Enum Types:**
- `location_type`: RESTAURANT, DELIVERY_BLOCK, HOME
- `order_status`: CREATED → CONFIRMED → PREPARING → READY_FOR_PICKUP → DRONE_ASSIGNED → IN_FLIGHT → DELIVERED / FAILED / CANCELLED
- `drone_status`: IDLE, RESERVED, ASSIGNED, IN_FLIGHT, RETURNING_HOME, CHARGING, MAINTENANCE
- `mission_status`: CREATED → ASSIGNED → IN_PROGRESS → DELIVERED → RETURNING_HOME → COMPLETED / FAILED

**Seed Data:**
- 5 HOME locations, 7 RESTAURANT locations, 5 DELIVERY_BLOCK locations
- 7 restaurants (Dominos, US Pizza, Chat & Chill, Paradise, Total Fresh, Baskin Robbins, Nescafe)
- 35 menu items with descriptions, prices, categories, and Unsplash images
- All GPS coordinates are real KL University campus locations

### Database Connection Options
| Environment | DATABASE_URL |
|------------|-------------|
| Local (no Docker) | `sqlite:///./orders.db` (automatic fallback) |
| Local Docker | `postgresql+asyncpg://skyro_admin:local_dev_pass@localhost:5432/skyro` |
| AWS RDS | `postgresql+asyncpg://skyro_admin:<pass>@skyro-db.cl4o2c2matz8.ap-south-1.rds.amazonaws.com:5432/skyro?sslmode=require` |

### 5.4 SQLite Mobile Database (Room DB Caching)
To support offline capabilities, the Android mobile client implements a local SQLite database using Jetpack Room with the following table mappings:
- **`CartItem`**: Persistent shopping cart.
- **`DeliveryOrder`**: Tracks active orders and histories locally. Extracted server order UUIDs are written to `serverOrderId` to map back to PostgreSQL.
- **`UserPreference`**: Configuration cache storing preferences, themes, active addresses, and overridden API endpoints.

---

## 6. Inter-Service Communication

### How Services Talk to Each Other

```
Frontend ──REST──► backend-orders (:8000)   [orders, restaurants, auth, payments]
Frontend ──REST──► backend (:8080)           [drone connect, launch, status]
Frontend ──REST──► backend-fleet-ai (:8002)  [fleet status]
Frontend ──WS────► backend-orders (:8000/ws) [order events]
Frontend ──WS────► backend (:8080/ws)        [drone telemetry]

backend ──REST──► backend-orders (:8000)     [mark order delivered]
backend ──REST──► backend-fleet-ai (:8002)   [reserve/release home pad]

backend-fleet-ai ──WS──► backend (:8080/ws)  [subscribe to drone telemetry]
backend-fleet-ai ──REST─► backend-orders     [fetch locations, persist reservations]
```

### WebSocket Channels

1. **Orders WS** (`:8000/ws`) — Pushes `order_created`, `order_updated`, `order_assigned` events
2. **Drone WS** (`:8080/ws`) — Pushes `status_update` (all drones every 2s), `mission_completed`, `mission_failed`, `obstacle_alert`, `landing_confirmed`
3. **Fleet AI WS** (`:8002/ws`) — Pushes `fleet_update` (drones + zones + conflicts every 2s)

---

## 7. Authentication & Payments

### Authentication (AWS Cognito)
- **Phone OTP:** `/api/auth/start` → Cognito CUSTOM_AUTH → `/api/auth/verify`
- **Email/Password:** `/api/auth/email/signup` → email confirmation code → `/api/auth/email/login`
- JWT tokens (access + ID + refresh) returned on success
- `/api/auth/me` verifies Bearer token and returns user info
- Env vars: `COGNITO_USER_POOL_ID`, `COGNITO_CLIENT_ID`, `AWS_REGION`

### Payments (Razorpay)
- `/api/payments/razorpay/order` creates a Razorpay order (amount in paise)
- `/api/payments/razorpay/verify` validates payment signature (HMAC-SHA256)
- Protected by Cognito JWT Bearer token
- Demo mode available via `VITE_DEMO_MODE=true` (skips real payment)
- Env vars: `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`

---

## 8. Docker Setup

### docker-compose.yml (5 services)

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `backend` | areodrone-backend | 8080 + 14550/udp | Drone MAVLink control |
| `backend-orders` | skyro-orders | 8000 | Orders/Data API |
| `backend-fleet-ai` | skyro-fleet-ai | 8002 | Fleet AI |
| `postgres` | postgres:15-alpine | 5432 | Local dev database |
| `redis` | redis:7-alpine | 6379 | Caching/pub-sub |

**Startup order:** `postgres` + `redis` start first → `backend` + `backend-orders` → `backend-fleet-ai` (depends on all three)

**DB auto-seed:** Docker mounts `db/schema.sql` and `db/seed.sql` into postgres `docker-entrypoint-initdb.d/` for automatic initialization.

### Running with Docker
```bash
docker-compose up --build        # Start everything
docker-compose up -d postgres    # Just the database
```

### Running Locally (without Docker)
```powershell
.\start-all.ps1    # Starts all 3 backends in separate PowerShell windows
# Then in frontend/:
npm run dev:user   # User app on :5173
npm run dev:vendor # Vendor app on :5174
npm run dev:admin  # Admin app on :5175
```

### Running Android Mobile App Locally
1. Open Android Studio and load the `Skyro_app` directory.
2. Create `Skyro_app/.env` with your `GEMINI_API_KEY`.
3. Set your active ngrok endpoints inside [NetworkConfig.kt](file:///c:/Users/SRMAP/Documents/Skyworks/Skyro/Skyro_app/app/src/main/java/com/example/data/NetworkConfig.kt) or override them via the Profile Screen settings.
4. Press **Run** to launch on a physical device or Google Play-enabled emulator.

---

## 9. AWS Production Infrastructure

| AWS Service | Purpose | Config |
|------------|---------|--------|
| **RDS (PostgreSQL 15)** | Primary database | `db.t3.micro`, `skyro-db`, ap-south-1 |
| **ElastiCache (Redis 7)** | Fleet state caching | `cache.t3.micro` |
| **ECS (Fargate)** | Container hosting | 3 task definitions |
| **ECR** | Docker image registry | 3 repos |
| **Cognito** | User authentication | User pool `skyro-users` |
| **Secrets Manager** | Credentials storage | DATABASE_URL, REDIS_URL |
| **API Gateway** | HTTP routing + JWT auth | Routes to ECS services |
| **CloudWatch** | Monitoring + alerts | Drone heartbeat alarm |
| **DynamoDB** | Telemetry logs | `DroneTelemetryLogs` table |
| **S3** | Flight path archives | `skyro-flight-archives` bucket |
| **SQS** | Async order events | `skyro-order-events` queue |

---

## 10. Environment Variables Summary

### Frontend (.env files)
| Variable | Description |
|----------|-------------|
| `VITE_API_BASE` | Orders backend URL (e.g., `http://localhost:8000`) |
| `VITE_DRONE_API_BASE` | Drone backend URL (e.g., ngrok URL or `http://localhost:8080`) |
| `VITE_VARIANT` | App mode: `user`, `vendor`, or `admin` |
| `VITE_DEMO_MODE` | `true` to skip real Razorpay payments |
| `VITE_MAPBOX_TOKEN` | Mapbox GL token for satellite map |
| `GEMINI_API_KEY` | Google Gemini API key (AI features) |

### Backend Services
| Variable | Service | Description |
|----------|---------|-------------|
| `DATABASE_URL` | orders, fleet-ai | PostgreSQL connection string |
| `REDIS_URL` | fleet-ai | Redis connection string |
| `ORDERS_API_BASE` | backend, fleet-ai | Orders service URL |
| `DRONE_BACKEND_URL` | fleet-ai | Drone backend HTTP URL |
| `DRONE_BACKEND_WS` | fleet-ai | Drone backend WebSocket URL |
| `CORS_ORIGINS` | all | Allowed CORS origins |
| `SAFE_THRESHOLD_M` | fleet-ai | Conflict detection distance (20m) |
| `PREDICT_SECONDS` | fleet-ai | Conflict lookahead time (7s) |
| `CRUISE_SPEED_MPS` | fleet-ai | Drone speed for ETA calc (5 m/s) |
| `COGNITO_USER_POOL_ID` | orders | AWS Cognito pool ID |
| `COGNITO_CLIENT_ID` | orders | AWS Cognito app client ID |
| `RAZORPAY_KEY_ID` | orders | Razorpay API key |
| `RAZORPAY_KEY_SECRET` | orders | Razorpay secret key |

---

## 11. Key Technical Decisions

1. **Three separate backends** — Microservice architecture allows independent scaling. Drone backend runs close to hardware; orders service can scale horizontally.

2. **Dual database support** — `database.py` auto-detects PostgreSQL vs SQLite. Development works without Docker; production uses AWS RDS.

3. **Custom asyncpg wrapper** — Instead of the `databases` library (which had SSL issues with RDS), a custom `_AsyncPGDatabase` class wraps asyncpg directly and compiles SQLAlchemy queries to positional `$1, $2` params.

4. **MAVSDK Migration and Semaphore Concurrency Guard** — Migrated the drone control backend from legacy, blocking DroneKit (Python 3.10) to MAVSDK-Python (Python 3.11). Integrated a shared `asyncio.Semaphore` to cap active connections, and decoupled telemetry streams into 4 isolated asyncio tasks per drone to handle 100+ concurrent drone telemetry connections efficiently without blocking the main event loop.

5. **Home pad reservation system** — 5 physical landing pads. Fleet AI reserves one for each returning drone to prevent collisions. Reservations are in-memory (fast) with async PostgreSQL persistence (durable).

6. **Atomic drone assignment** — `assign_drone_to_order` uses `UPDATE ... WHERE assigned_drone_id IS NULL` to prevent double-dispatch race conditions.

7. **PWA support** — Frontend is installable as a Progressive Web App with offline caching, making it feel native on mobile devices.

---

## 12. Complete Order Lifecycle

```
[User places order]
     │
     ▼
  PLACED (CREATED) ─── saved to PostgreSQL, broadcast via WS
     │
     ▼
  ACCEPTED (CONFIRMED) ─── vendor accepts in VendorView
     │
     ▼
  COOKING (PREPARING) ─── vendor marks food being prepared
     │
     ▼
  READY FOR LAUNCH (READY_FOR_PICKUP) ─── food ready
     │
     ▼
  [Admin clicks "Launch Drone"]
     │
     ├─► Fleet AI scores drones → assigns best one
     ├─► Authorization: 4 safety checks
     ├─► POST /api/launch to drone backend
     │
     ▼
  EN ROUTE (IN_FLIGHT) ─── drone armed, flying to block
     │
     ├─► Drone arrives at block GPS
     ├─► Lands, disarms
     ├─► Servo drops payload
     ├─► Re-arms, requests home pad
     ├─► Flies to assigned home
     ├─► Lands at home, releases pad
     │
     ▼
  DELIVERED ─── backend PATCHes orders service
     │
     ▼
  [User gets notification, order complete]
```

---

*Document generated: June 2026 | Project: Skyro Drone Delivery System | Campus: SRM University, Amaravati*
