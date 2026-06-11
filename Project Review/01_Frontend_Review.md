# SKYRO — Frontend Review

> Complete documentation of the Skyro Web Frontend: architecture, components, state management, API integration, and every screen in the web apps. For details on the native Android mobile application, see [05_Mobile_App_Review.md](./05_Mobile_App_Review.md).

---

## 1. Tech Stack

| Technology | Version | Purpose |
|-----------|---------|---------|
| React | 19.1.1 | UI framework |
| TypeScript | 5.8.2 | Type safety |
| Vite | 6.2.0 | Build tool + dev server |
| TailwindCSS | 3.4.17 | Utility-first CSS |
| React Router DOM | 7.13.0 | Client-side routing |
| Framer Motion | 12.34.0 | Animations |
| Leaflet + React-Leaflet | 1.9.4 / 5.0.0 | Schematic map rendering |
| Mapbox GL | 3.18.1 | Satellite map rendering |
| Lucide React | 0.563.0 | Icon library |
| QRCode React | 4.2.0 | QR code generation |
| vite-plugin-pwa | 1.2.0 | Progressive Web App support |

---

## 2. Three App Variants (One Codebase)

The frontend is a **single React codebase** that serves three different apps based on the `VITE_VARIANT` environment variable:

| Variant | .env File | Port | What It Shows |
|---------|-----------|------|---------------|
| **User** | `.env.user` | 5173 | Food ordering, payment, live tracking |
| **Vendor** | `.env.vendor` | 5174 | Restaurant order management dashboard |
| **Admin** | `.env.admin` | 5175 | Fleet management, drone control, map |

### How It Works

**`vite.config.ts`** reads the mode from the `.env` file:
```typescript
const variant = env.VITE_VARIANT || mode;
const ports = { user: 5173, vendor: 5174, admin: 5175 };
```

**`App.tsx`** checks `VITE_VARIANT` and renders the correct view:
```typescript
const variant = import.meta.env.VITE_VARIANT; // 'user' | 'vendor' | 'admin'
switch (activeView) {
    case 'user':   return <UserView />;
    case 'vendor': return <VendorView />;
    case 'admin':  return <AdminView />;
}
```

### Environment Variables

**`.env.user`:**
```
VITE_API_BASE=http://localhost:8000          # Orders backend
VITE_VARIANT=user
VITE_DEMO_MODE=true                          # Skip real payments
VITE_DRONE_API_BASE=http://localhost:8080    # Drone backend (or ngrok URL)
VITE_MAPBOX_TOKEN=pk.eyJ1...                 # Mapbox satellite map token
```

**`.env.vendor`:**
```
VITE_API_BASE=http://localhost:8000
VITE_VARIANT=vendor
VITE_DRONE_API_BASE=http://localhost:8080
```

**`.env.admin`:**
```
VITE_API_BASE=http://localhost:8000
VITE_VARIANT=admin
VITE_DRONE_API_BASE=http://localhost:8080
```

### Build Commands
```bash
npm run dev:user      # Dev server for user variant
npm run dev:vendor    # Dev server for vendor variant
npm run dev:admin     # Dev server for admin variant
npm run build:user    # Production build → dist/user/
npm run build:vendor  # Production build → dist/vendor/
npm run build:admin   # Production build → dist/admin/
```

---

## 3. Component Architecture

```
App.tsx
 ├── AppProvider (context/AppContext.tsx)
 │    └── Central state: orders, drones, restaurants, menus, locations
 │
 ├── NotificationContainer
 │    └── Toast notifications (info/success/warning/error)
 │
 ├── UserView.tsx ───────────────────────── (VITE_VARIANT=user)
 │    ├── LoginScreen.tsx        # AWS Cognito login (phone/email)
 │    ├── SignupScreen.tsx       # Registration with email verification
 │    ├── HomeScreen.tsx         # Restaurant catalogue (Swiggy-style)
 │    │    └── SwiggyHomeScreen  # Premium restaurant cards
 │    ├── RestaurantDetail.tsx   # Menu browsing + add to cart
 │    ├── CartDrawer.tsx         # Sliding cart panel
 │    ├── BlockScreen.tsx        # Delivery location picker
 │    ├── PaymentScreen.tsx      # Razorpay checkout
 │    ├── OrdersScreen.tsx       # Order history with status colors
 │    ├── TrackingScreen.tsx     # Live drone tracking on Mapbox map
 │    ├── DeliveryMap.tsx        # Route visualization
 │    └── ProfileScreen.tsx      # User profile
 │
 ├── VendorView.tsx ─────────────────────── (VITE_VARIANT=vendor)
 │    └── Incoming orders list with Accept/Decline/Cook/Ready buttons
 │
 ├── AdminView.tsx ──────────────────────── (VITE_VARIANT=admin)
 │    ├── Drone fleet panel (connect/disconnect/status)
 │    ├── Order management (launch drone for ready orders)
 │    ├── Activity log
 │    └── Map.tsx (Leaflet + Mapbox live map with drone positions)
 │
 ├── Map.tsx ────────────────────────────── Shared map component
 │    └── Leaflet schematic / Mapbox satellite toggle
 │
 ├── Header.tsx ─────────────────────────── App header bar
 └── Icons.tsx ──────────────────────────── SVG icon components
```

---

## 4. State Management (AppContext.tsx)

`AppContext.tsx` is the **single central state manager** for the entire app. It's a React Context Provider that holds all data and exposes all actions.

### State Variables

| State | Type | Source |
|-------|------|--------|
| `orders` | `Order[]` | Loaded from API on startup, updated via WebSocket |
| `drones` | `Drone[]` | Initialized from `INITIAL_DRONES`, updated by WS + polling |
| `restaurants` | `RestaurantData[]` | Fetched from `/api/restaurants` via `useRestaurants()` hook |
| `menuItems` | `MenuItemData[]` | Fetched from `/api/menu-items` via `useMenuItems()` hook |
| `deliveryLocations` | `DeliveryLocationData[]` | Fetched from `/api/locations?type=DELIVERY_BLOCK` |
| `activityLog` | `string[]` | Timestamped log entries (last 100) |
| `notifications` | `Notification[]` | Toast notifications with auto-dismiss (5s) |
| `mapStyle` | `'schematic' \| 'satellite'` | Map rendering mode toggle |

### Exposed Functions

| Function | What It Does |
|----------|-------------|
| `placeOrder(userId, cart, total, locationId, restaurantId)` | POST to `/api/orders`, falls back to in-memory if no API |
| `updateOrderStatus(orderId, status)` | PATCH to `/api/orders/{id}`, optimistic local update |
| `launchDroneForOrder(orderId)` | Finds idle drone → resolves block GPS → POST to `/api/launch` |
| `connectToDrone(droneId)` | POST to `/api/connect` on drone backend |
| `disconnectFromDrone(droneId)` | DELETE to `/api/drones/{id}` on drone backend |
| `commandRtl(droneId)` | Manually command Return-to-Launch |
| `updateDroneConnectionString(droneId, value)` | Edit drone's UDP/serial connection string |
| `toggleMapStyle()` | Switch between Leaflet schematic and Mapbox satellite |

### WebSocket Connections (Automatic)

The AppContext establishes **two WebSocket connections** on mount:

**1. Orders WebSocket** (`backend-orders:8000/ws`):
```
Listens for:
  • order_created  → adds new order to state
  • order_updated  → updates order status, triggers "Delivered" notification
```

**2. Drone WebSocket** (`backend:8080/ws`):
```
Listens for:
  • status_update  → updates drone position, battery, armed status
  • Drone positions update on the map in real-time
```

### HTTP Polling (Fallback)

Every 2 seconds, the app polls each connected drone's status via `POST /api/status`. This provides redundancy if the WebSocket disconnects.

### Offline/Simulation Mode

If `VITE_API_BASE` is not configured, the app runs in **offline simulation mode**:
- Orders are stored in-memory only
- Drones move along simulated paths on the map (calculated every 100ms)
- No backend connection needed — useful for UI development

---

## 5. Data Fetching Hooks (`useAppData.ts`)

Three custom hooks fetch live data from the orders backend:

### `useRestaurants()`
```typescript
// Fetches from: GET {VITE_API_BASE}/api/restaurants
// Returns: { restaurants: RestaurantData[], loading: boolean }
// Data includes: id, name, tagline, rating, cuisine, delivery_time_min,
//                price_for_two, offer, image_url, latitude, longitude
```

### `useMenuItems()`
```typescript
// Fetches from: GET {VITE_API_BASE}/api/menu-items
// Returns: { menuItems: MenuItemData[], loading: boolean }
// Data includes: id, restaurant_id, name, description, price,
//                category, image_url, is_available
```

### `useDeliveryLocations()`
```typescript
// Fetches from: GET {VITE_API_BASE}/api/locations?type=DELIVERY_BLOCK
// Returns: { locations: DeliveryLocationData[], loading: boolean }
// Data includes: id, name, type, latitude, longitude
```

If the API is unreachable, the app falls back to hardcoded data in `constants.ts`.

---

## 6. TypeScript Types (`types.ts`)

### Enums

```typescript
enum OrderStatus {
  PLACED = 'Placed',
  DECLINED = 'Declined',
  ACCEPTED = 'Accepted',
  COOKING = 'Cooking',
  READY_FOR_LAUNCH = 'Ready for Launch',
  EN_ROUTE = 'En Route',
  DELIVERED = 'Delivered',
  FAILED = 'Failed',
}

enum DroneStatus {
  IDLE = 'Idle',
  ON_MISSION = 'On Mission',
  RETURNING_HOME = 'Returning Home',
  CHARGING = 'Charging',
  MAINTENANCE = 'Maintenance',
}
```

### Key Interfaces

```typescript
interface Order {
  id: string;                    // "ORD-1712345678901"
  user: string;                  // User ID
  restaurantId: string;          // Restaurant UUID
  items: CartItem[];             // Ordered items with quantities
  total: number;                 // Total price
  deliveryLocationId: string;    // Delivery block ID
  status: OrderStatus;           // Current status
  createdAt: Date;
  droneId?: string;              // Assigned drone ID
}

interface Drone {
  id: string;                    // "D-01"
  model: string;                 // "Aero-1"
  status: DroneStatus;
  battery: number;               // 0-100%
  location: Coordinates;         // Current GPS
  homeLocation: Coordinates;     // Home pad GPS
  destination?: Coordinates;     // Target GPS
  mission?: 'DELIVERY' | 'RETURN';
  isConnected: boolean;
  connectionString: string;      // "udp:127.0.0.1:14550"
}

interface Restaurant {
  id: string;
  name: string;
  location: Coordinates;
  rating?: number;
  deliveryTime?: string;
  cuisine?: string;
  priceForTwo?: number;
  offer?: string;
}
```

---

## 7. Key Screens In Detail

### HomeScreen (User)
- Displays restaurant catalogue in a Swiggy-style card layout
- Each card shows: name, cuisine, rating, delivery time, price for two, offer badge
- Restaurant images loaded from Unsplash URLs (stored in PostgreSQL seed data)
- Search and filter capabilities

### RestaurantDetail (User)
- Shows restaurant header with full details
- Menu items grouped by category (Pizza, Desserts, Beverages, etc.)
- "Add to Cart" button on each item
- Cart item count badge in header

### CartDrawer (User)
- Sliding panel from the right
- Shows all cart items with +/- quantity controls
- Running total calculation
- "Proceed to Checkout" → navigates to BlockScreen

### TrackingScreen (User)
- Full-screen Mapbox satellite map
- Shows: restaurant location (pickup), delivery block (destination), drone position (live)
- Animated drone path line
- Real-time position updates via WebSocket
- ETA display

### VendorView
- List of incoming orders with status badges
- Action buttons per order: Accept, Decline, Mark Cooking, Mark Ready
- Each status change sends PATCH to orders backend

### AdminView
- **Drone Fleet Panel:** Shows all 3 drones with status, battery, connection string editor, connect/disconnect buttons
- **Orders Panel:** Lists all orders, "Launch Drone" button for "Ready for Launch" orders
- **Activity Log:** Scrollable timestamped log of all system events
- **Live Map:** Leaflet/Mapbox map showing drone positions, home pads, restaurant and delivery block markers

---

## 8. PWA Configuration

The app is a **Progressive Web App** — installable on mobile devices:

```typescript
// vite.config.ts — VitePWA plugin
manifest: {
  name: 'Skyro',
  short_name: 'Skyro',
  description: 'Skyro Campus Food Ordering',
  display: 'standalone',
  background_color: '#0b1220',
  theme_color: '#0b1220',
  icons: [
    { src: '/icons/icon-192.png', sizes: '192x192' },
    { src: '/icons/icon-512.png', sizes: '512x512' },
    { src: '/icons/maskable-512.png', sizes: '512x512', purpose: 'maskable' },
  ],
}
```

Workbox caching strategy:
- **Images:** CacheFirst (cached for 30 days, max 200 entries)
- **Pages:** NetworkFirst (always try network, fall back to cache)

---

## 9. Map Implementation

### Dual Map Engine
The app supports two map modes, toggled by the user:

**Schematic Mode (Leaflet):**
- Uses OpenStreetMap tiles
- Lightweight, fast loading
- Markers for drones, restaurants, delivery blocks, home pads

**Satellite Mode (Mapbox GL):**
- Uses Mapbox satellite imagery
- Requires `VITE_MAPBOX_TOKEN`
- Better visual context for campus navigation
- Used in TrackingScreen for delivery tracking

### Map Markers
- 🏠 Home pads (5 locations) — green markers
- 🍕 Restaurants (7 locations) — orange markers
- 📍 Delivery blocks (5 locations) — blue markers
- 🚁 Active drones — animated markers with heading

---

## 10. Initial Drone Configuration

Three drones are pre-configured in `constants.ts`:

| Drone ID | Model | Connection String | Home Pad |
|----------|-------|-------------------|----------|
| D-01 | Aero-1 | `udp:127.0.0.1:14550` | HOME_1 |
| D-02 | Aero-1 | `udp:127.0.0.1:14551` | HOME_2 |
| D-03 | Aero-2 | `udp:127.0.0.1:14552` | HOME_3 |

Connection strings are editable in the Admin panel before connecting.

---

*Document generated: May 2026 | Project: Skyro Drone Delivery System | Campus: SRM University, Amaravati*
