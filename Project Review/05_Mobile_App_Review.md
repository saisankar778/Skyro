# SKYRO — Mobile App Review

> Complete documentation of the Skyro native Android application: architecture, screens, components, local Room database caching, API Retrofit interfaces, and real-time WebSocket telemetry syncing.

---

## 1. Tech Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| **Kotlin** | 1.9.0 | Primary programming language |
| **Jetpack Compose** | 1.5.4 | Native UI framework |
| **Retrofit** | 2.9.0 | HTTP client for REST API communication |
| **Moshi** | 1.15.0 | JSON parsing and serialization |
| **OkHttp3** | 4.12.0 | HTTP engine & WebSocket connection manager |
| **Room Database** | 2.6.1 | SQLite ORM for local caching and offline operations |
| **Google Play Services Maps** | 18.2.0 | Live drone telemetry GPS mapping |
| **Coroutines & Flow** | 1.7.3 | Async programming and reactive data streams |

---

## 2. Component & Screen Architecture

The Android app is built using the **MVVM (Model-View-ViewModel)** architectural pattern. It consists of a single activity (`MainActivity`) rendering dynamic screens via Compose animations, backed by repositories and local database layers.

```
MainActivity.kt
 ├── SkyroViewModel & LocationViewModel (ViewModels)
 │    └── Exposes StateFlows: cartItems, activeOrders, userPreferences, droneLocationsMap
 │
 ├── MyApplicationTheme (ui/theme/Theme.kt)
 │    └── Supports Light (WarmCream) / Dark (MidnightNav) themes
 │
 └── Screen Navigation Flow (AnimatedContent)
      ├── SplashScreen           # Intro screen with status/GPS checks
      ├── OnboardingScreen       # First-use welcome pages
      ├── LoginScreen            # Quick credentials entry
      ├── HomeScreen             # Categories + restaurant carousel
      │    └── BottomNavBar      # Sticky bottom navigation bar
      ├── RestaurantDetailScreen # Full canteen menu + item options
      ├── CartScreen             # Cart items edit + checkout actions
      ├── CinematicSequenceScreen# Multi-stage flight simulation video playback
      ├── LiveTrackingScreen     # Live Google Map drawing drone markers & telemetry
      ├── OrdersHistoryScreen    # Historic orders + Quick Reorder button
      ├── ProfileScreen          # Personal details + AWS API configuration
      └── OfflineScreen          # Connection failure page with retry trigger
```

---

## 3. Data & Storage Layer (Room DB)

The app features a fully offline-capable architecture using a local SQLite database powered by **Room**. This stores cart states, user configurations, and syncs order statuses.

### 3.1 Entities (`Entities.kt`)

*   **`CartItem`**: Stores items added to the cart, capturing name, price, quantity, restaurant name, restaurant UUID, and menu item ID.
*   **`DeliveryOrder`**: Local order log caching `orderId`, `restaurantName`, list items summary, `totalPrice`, `droneId`, `etaMinutes`, `status` (PREPARING, ACCEPTED, COOKING, READY_FOR_LAUNCH, IN_FLIGHT, DELIVERED, DECLINED, FAILED), `serverOrderId` (maps back to the AWS/ngrok PostgreSQL entry), and `deliveryLocationName`.
*   **`UserPreference`**: Configuration cache storing `isLoggedIn`, user details (`userName`, `phoneNumber`, `userEmail`), local `address`, `awsApiUrl` (custom endpoint URL), `themeMode` (SUNNY, SKYRO_PRESENT, NIGHT), `selectedDeliveryLocationId`, and `selectedDeliveryLocationName`.

### 3.2 DAOs (`Daos.kt`)

The `SkyroDao` interface exposes Kotlin Coroutine `Flows` to automatically propagate state updates to UI elements:
*   `getCartItems()`: Emits `List<CartItem>` reactive stream.
*   `getAllOrders()` / `getActiveOrders()`: Emits historical and active delivery tracking entries.
*   `getUserPreferenceFlow()`: Emits configuration settings.
*   `updateOrderStatus()`: Atomic status synchronization.

---

## 4. API and Network Integration

All remote communications are defined in `SkyroApiService.kt` and managed via a singleton client (`SkyroRetrofitClient`).

### 4.1 Retrofit API Calls
*   `GET api/restaurants`: Fetches available canteens.
*   `GET api/menu-items?restaurant_id=xxx`: Fetches dishes for a restaurant.
*   `GET api/locations?type=DELIVERY_BLOCK`: Obtains campus GPS destinations.
*   `GET api/orders`: Downloads history.
*   `POST api/orders`: Submits a new checkout payload (`ApiOrderCreateRequest`).
*   `PATCH api/orders/{id}`: Submits status updates to the server.

### 4.2 Handling ngrok Browser Warnings (Critical)
During development and simulation, the backend is tunneled through `ngrok`. Because ngrok presents an HTML warning page for browser traffic, Moshi parser will crash. To bypass this, OkHttp interceptors inject a custom header to every request:
```kotlin
val ngrokInterceptor = Interceptor { chain ->
    val request = chain.request().newBuilder()
        .addHeader(NetworkConfig.NGROK_HEADER_NAME, NetworkConfig.NGROK_HEADER_VALUE) // ngrok-skip-browser-warning = true
        .build()
    chain.proceed(request)
}
```

---

## 5. WebSocket & Real-Time Sync

The app handles **two distinct WebSocket connections** using OkHttp to provide real-time updates:

### 5.1 Orders WebSocket (`/ws` on Orders Service)
*   **Goal**: Monitor order transitions (Accept → Cook → Ready).
*   **Behavior**: When a `status_update` or `order_updated` JSON packet is received:
    1. It extracts the `status` and `droneId`.
    2. Room database is updated via `repository.updateOrderStatus()`.
    3. StateFlows emit the updated status to refresh the cart and tracking screens.

### 5.2 Telemetry WebSocket (`/ws` on Drone Backend)
*   **Goal**: Drive live GPS positions of active drones on Google Maps.
*   **Behavior**:
    *   Subscribes to port `8080/ws` (or ngrok forwarding port).
    *   Receives `status_update` payloads containing exact GPS lat/lon of connected drones.
    *   Maps coordinate properties to a reactive state `_droneLocationsMap` containing `Map<String, LatLng>` objects.
    *   Draws custom animated drone symbols on the Google Map in `LiveTrackingScreen`.

---

## 6. Key Screens In Detail

### 6.1 HomeScreen
*   Displays campus restaurant options loaded from the API.
*   Shows active discount banners, delivery times, and ratings.
*   Displays horizontal food categories (Pizza, Biryani, Desserts) that filter menu items instantly.
*   Floating active order tracker if a drone is currently en route.

### 6.2 RestaurantDetailScreen
*   Renders menu cards with category headers.
*   Features quick +/- add-to-cart buttons.
*   Calculates cart weight (in grams) to prevent overloading drone payloads.

### 6.3 CartScreen
*   Shows selected dishes and pricing breakdown (Items total + GST + Drone Delivery Fee + Platform Fee).
*   Allows selecting campus delivery block (SR Block, C Block, Admin Block, etc.).
*   Triggers order placement via Retrofit and launches the flight map.

### 6.4 LiveTrackingScreen
*   Embeds a high-performance Google Map.
*   Places markers for: Restaurant (pickup point), Delivery Block (target pad), and Drone (real-time telemetry coordinate).
*   Draws a route line path mapping the drone's trajectory.
*   Displays order status, telemetry metrics (altitude, speed, drone model), and an ETA countdown.

### 6.5 ProfileScreen
*   Enables manual override of the AWS API Gateway base URL to swap between Local Dev, ngrok tunnels, and Production AWS servers.
*   Theme switcher for Light, Dark (Night Mode), and campus custom styles.

---

## 7. Local Configuration

The app relies on two central configurations:
1.  **`.env`**: Must be placed in the project root containing `GEMINI_API_KEY=AIza...` for AI-assisted UI.
2.  **`NetworkConfig.kt`**: Defines default fallbacks:
    *   `DEFAULT_BASE_URL`: Orders service API url.
    *   `DEFAULT_DRONE_BASE_URL`: MAVLink telemetry API url.

---

*Document generated: June 2026 | Project: Skyro Drone Delivery System | Mobile Client: Android Compose*
