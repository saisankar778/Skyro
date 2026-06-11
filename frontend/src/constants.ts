import { Restaurant, MenuItem, DeliveryLocation, Drone, DroneStatus, OrderStatus, Coordinates } from './types';

// ============================================================
// ⚠️  SINGLE SOURCE OF TRUTH — All GPS data matches db/seed.sql
// ============================================================

// ─── Home landing pads (5 pads, same as seed.sql HOME locations) ─────────────
export const HOME_LOCATIONS: Coordinates[] = [
  { lat: 16.46279507215054, lon: 80.50735459755417 }, // HOME_1
  { lat: 16.462866449965045, lon: 80.50755119683426 }, // HOME_2
  { lat: 16.462835582985836, lon: 80.50771749378666 }, // HOME_3
  { lat: 16.462856160972517, lon: 80.50792670608162 }, // HOME_4
  { lat: 16.462677389639875, lon: 80.50761959315294 }, // HOME_5
];
export const HOME_LOCATION: Coordinates = HOME_LOCATIONS[0]; // Default fallback

// ─── Delivery block coordinates (matches seed.sql DELIVERY_BLOCK) ────────────
export const BLOCK_COORDINATES: Record<string, Coordinates> = {
  SR_Block: { lat: 16.462635294684286, lon: 80.50647168669644 },
  C_Block: { lat: 16.461646855350896, lon: 80.50569336570064 },
  Admin_Block: { lat: 16.464874583335895, lon: 80.50791898212552 },
  Yamuna_Hostel: { lat: 16.466254271237375, lon: 80.50757917761362 },
  V_and_G_Hostels: { lat: 16.463886777402795, lon: 80.50665800799868 },
};

// ─── Delivery locations shown in frontend dropdowns ──────────────────────────
export const DELIVERY_LOCATIONS: DeliveryLocation[] = [
  { id: 'SR_Block', name: 'SR Block', location: BLOCK_COORDINATES.SR_Block },
  { id: 'C_Block', name: 'C Block', location: BLOCK_COORDINATES.C_Block },
  { id: 'Admin_Block', name: 'Admin Block', location: BLOCK_COORDINATES.Admin_Block },
  { id: 'Yamuna_Hostel', name: 'Yamuna Hostel', location: BLOCK_COORDINATES.Yamuna_Hostel },
  { id: 'V_and_G_Hostels', name: 'V & G Hostels', location: BLOCK_COORDINATES.V_and_G_Hostels },
];

// ─── Restaurants (matches seed.sql RESTAURANT locations) ─────────────────────
export const RESTAURANTS: Restaurant[] = [
  {
    id: 'Dominos',
    name: "Domino's Pizza",
    location: { lat: 16.463084574257913, lon: 80.5084325541339 },
    rating: 4.3,
    deliveryTime: '20-30 min',
    cuisine: 'Pizza, Fast Food',
    priceForTwo: 400,
    offer: '50% OFF',
  },
  {
    id: 'US_Pizza',
    name: 'US Pizza',
    location: { lat: 16.46277461846416, lon: 80.50822267128899 },
    rating: 4.2,
    deliveryTime: '25-30 min',
    cuisine: 'Pizza, Italian',
    priceForTwo: 500,
    offer: 'Buy 1 Get 1',
  },
  {
    id: 'Chat_and_Chill',
    name: 'Chat & Chill',
    location: { lat: 16.462954675830282, lon: 80.50807783200786 },
    rating: 4.5,
    deliveryTime: '10-15 min',
    cuisine: 'Street Food, Snacks',
    priceForTwo: 200,
    offer: 'Free Coke',
  },
  {
    id: 'Paradise',
    name: 'Paradise',
    location: { lat: 16.46286593329217, lon: 80.50807313814228 },
    rating: 4.7,
    deliveryTime: '15-20 min',
    cuisine: 'Biryani, Indian',
    priceForTwo: 350,
    offer: 'Free Raita',
  },
  {
    id: 'Total_Fresh',
    name: 'Total Fresh',
    location: { lat: 16.463118656500374, lon: 80.50826089276595 },
    rating: 4.1,
    deliveryTime: '10-15 min',
    cuisine: 'Healthy, Juices',
    priceForTwo: 180,
    offer: '15% OFF',
  },
  {
    id: 'Baskin_Robins',
    name: 'Baskin Robbins',
    location: { lat: 16.463022197299473, lon: 80.50831923080973 },
    rating: 4.4,
    deliveryTime: '10-12 min',
    cuisine: 'Ice Cream, Desserts',
    priceForTwo: 250,
    offer: '10% OFF',
  },
  {
    id: 'Nescafe',
    name: 'Nescafe',
    location: { lat: 16.46288008065604, lon: 80.50844663573295 },
    rating: 4.0,
    deliveryTime: '5-10 min',
    cuisine: 'Coffee, Snacks',
    priceForTwo: 150,
    offer: 'Free Cookie',
  },
];

// ─── Menu items ───────────────────────────────────────────────────────────────
export const MENU_ITEMS: MenuItem[] = [
  { id: 'item-d1', name: 'Farmhouse Pizza', price: 350, restaurantId: 'Dominos' },
  { id: 'item-d2', name: 'Peppy Paneer', price: 390, restaurantId: 'Dominos' },
  { id: 'item-d3', name: 'Margherita', price: 280, restaurantId: 'Dominos' },
  { id: 'item-u1', name: 'Double Cheese Pizza', price: 400, restaurantId: 'US_Pizza' },
  { id: 'item-u2', name: 'BBQ Chicken Pizza', price: 450, restaurantId: 'US_Pizza' },
  { id: 'item-c1', name: 'Paneer Tikka Roll', price: 120, restaurantId: 'Chat_and_Chill' },
  { id: 'item-c2', name: 'Aloo Tikki', price: 60, restaurantId: 'Chat_and_Chill' },
  { id: 'item-c3', name: 'Samosa', price: 40, restaurantId: 'Chat_and_Chill' },
  { id: 'item-p1', name: 'Chicken Biryani', price: 180, restaurantId: 'Paradise' },
  { id: 'item-p2', name: 'Mutton Biryani', price: 220, restaurantId: 'Paradise' },
  { id: 'item-t1', name: 'Fresh Lime Juice', price: 60, restaurantId: 'Total_Fresh' },
  { id: 'item-t2', name: 'Fruit Salad', price: 90, restaurantId: 'Total_Fresh' },
  { id: 'item-b1', name: 'Mississippi Mud Pie', price: 120, restaurantId: 'Baskin_Robins' },
  { id: 'item-b2', name: 'Cotton Candy Blast', price: 90, restaurantId: 'Baskin_Robins' },
  { id: 'item-n1', name: 'Cold Coffee', price: 80, restaurantId: 'Nescafe' },
  { id: 'item-n2', name: 'Veg Sandwich', price: 70, restaurantId: 'Nescafe' },
];

// ─── Initial drones (3 drones on UDP 14550/51/52) ────────────────────────────
export const INITIAL_DRONES: Drone[] = [
  { id: 'D-01', model: 'Aero-1', status: DroneStatus.IDLE, battery: 98, location: HOME_LOCATIONS[0], homeLocation: HOME_LOCATIONS[0], isConnected: false, connectionString: 'udp:127.0.0.1:14550' },
  { id: 'D-02', model: 'Aero-1', status: DroneStatus.IDLE, battery: 100, location: HOME_LOCATIONS[1], homeLocation: HOME_LOCATIONS[1], isConnected: false, connectionString: 'udp:127.0.0.1:14551' },
  { id: 'D-03', model: 'Aero-2', status: DroneStatus.CHARGING, battery: 45, location: HOME_LOCATIONS[2], homeLocation: HOME_LOCATIONS[2], isConnected: false, connectionString: 'udp:127.0.0.1:14552' },
];

// ─── Status colour maps ───────────────────────────────────────────────────────
export const STATUS_COLORS: { [key in OrderStatus]: string } = {
  [OrderStatus.PLACED]: 'bg-blue-500',
  [OrderStatus.DECLINED]: 'bg-red-600',
  [OrderStatus.ACCEPTED]: 'bg-cyan-500',
  [OrderStatus.COOKING]: 'bg-yellow-500',
  [OrderStatus.READY_FOR_LAUNCH]: 'bg-purple-500',
  [OrderStatus.EN_ROUTE]: 'bg-indigo-500',
  [OrderStatus.DELIVERED]: 'bg-green-500',
  [OrderStatus.FAILED]: 'bg-red-800',
};

export const DRONE_STATUS_COLORS: { [key in DroneStatus]: string } = {
  [DroneStatus.IDLE]: 'bg-green-500',
  [DroneStatus.ON_MISSION]: 'bg-indigo-500',
  [DroneStatus.RETURNING_HOME]: 'bg-sky-500',
  [DroneStatus.CHARGING]: 'bg-yellow-500',
  [DroneStatus.MAINTENANCE]: 'bg-red-500',
};

