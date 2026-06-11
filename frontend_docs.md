# Skyro Frontend Architecture Documentation

## Overview

The Skyro frontend is a modern single-page application (SPA) built using **React, TypeScript, Vite, and TailwindCSS**. It acts as the user interface for all stakeholders in the drone delivery ecosystem. 

Because a drone delivery network involves different types of users with vastly different needs, the frontend is designed to support multiple "portals" or environments, specifically divided into **Admin**, **Vendor** (Restaurant), and **User** (Customer) views.

---

## Project Structure & Tooling

- **Framework**: React with TypeScript for type safety.
- **Bundler**: Vite (chosen for fast HMR and optimized production builds).
- **Styling**: TailwindCSS (`tailwind.config.cjs`, `index.css`) for utility-first, responsive, and rapid UI development.
- **Package Manager**: Bun (`bun.lock`) / NPM (`package-lock.json`).

### Environment Configuration

The frontend relies heavily on environment variables to dictate its build mode and API connections. There are three primary environment files:

1. **`.env.user`**: Configurations specific to the customer-facing app (ordering food, tracking drones).
2. **`.env.vendor`**: Configurations for restaurant partners (accepting orders, updating food status).
3. **`.env.admin`**: Configurations for the system administrators (fleet monitoring, manual drone overrides, system health).

**Key Environment Variables:**
- `VITE_API_BASE`: Points to the deployed `backend-orders` service (e.g., `https://areodrone-database.onrender.com` or local `http://localhost:8000`).
- `VITE_DRONE_API_BASE`: Points to the `backend` service for real-time MAVLink interactions (e.g., `http://127.0.0.1:8080`).

---

## Stakeholder Portals (Workflow)

### 1. User App (Customer Workflow)
- **Browsing:** Users fetch lists of restaurants and menu items (served by `backend-orders`).
- **Ordering:** Users place an order and check out. The frontend creates a transaction in the database.
- **Tracking:** Once the order is in flight, the frontend establishes a WebSocket connection or polls the API to render a live map showing the drone's GPS coordinates moving towards the `drop_location_id`.

### 2. Vendor App (Restaurant Workflow)
- **Order Management:** Vendors receive real-time notifications of new orders.
- **Preparation:** They can accept orders and toggle the status to `PREPARING`.
- **Dispatching:** Once food is packed, the vendor marks the order as `READY_FOR_PICKUP`. This status change triggers the backend Fleet AI to dispatch a drone to the vendor's `pickup_location_id`.

### 3. Admin App (Fleet Management)
- **Global Map:** Displays the real-time telemetry of all drones in the network, utilizing connections to `backend-fleet-ai` and `backend`.
- **Intervention:** Allows admins to view active warnings (e.g., AI collision avoidance triggers) and manually connect to drones via UDP/Serial connections (e.g., `udp:127.0.0.1:14550`).
- **System Health:** Monitors database status, active orders, and drone battery levels.

---

## Network Communication

- **REST APIs**: Standard `fetch` or `axios` calls are made to `backend-orders` for static or standard transactional data (CRUD operations).
- **WebSockets**: Used heavily on the Admin and User tracking views to stream live MAVLink telemetry from the drone `backend` without the overhead of HTTP polling, ensuring smooth map animations.
