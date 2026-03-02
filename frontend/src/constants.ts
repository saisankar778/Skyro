import { Restaurant, MenuItem, DeliveryLocation, Drone, DroneStatus, OrderStatus, Coordinates } from './types';

export const RESTAURANTS: Restaurant[] = [
  {
    id: 'rest-dominos',
    name: "Domino's Pizza",
    location: { lat: 16.459, lon: 80.506 },
    rating: 4.5,
    deliveryTime: '20-30 min',
    cuisine: 'Pizza, Fast Food',
    priceForTwo: 400,
    offer: '50% OFF'
  },
  {
    id: 'rest-waffle',
    name: 'The Belgian Waffle Co.',
    location: { lat: 16.465, lon: 80.509 },
    rating: 4.8,
    deliveryTime: '15-20 min',
    cuisine: 'Waffles, Desserts',
    priceForTwo: 300,
    offer: '20% OFF'
  },
  {
    id: 'rest-chat',
    name: 'Chat & Chill',
    location: { lat: 16.462, lon: 80.508 },
    rating: 4.2,
    deliveryTime: '10-15 min',
    cuisine: 'Street Food, Snacks',
    priceForTwo: 200,
    offer: 'Free Coke'
  },
  {
    id: 'rest-uspizza',
    name: 'US Pizza',
    location: { lat: 16.461, lon: 80.507 },
    rating: 4.0,
    deliveryTime: '25-30 min',
    cuisine: 'Pizza, Italian',
    priceForTwo: 500,
    offer: 'Buy 1 Get 1'
  },
  {
    id: 'rest-br',
    name: 'Baskin Robbins',
    location: { lat: 16.463, lon: 80.506 },
    rating: 4.9,
    deliveryTime: '10-12 min',
    cuisine: 'Ice Cream, Desserts',
    priceForTwo: 250,
    offer: '10% OFF'
  },
];

export const MENU_ITEMS: MenuItem[] = [
  { id: 'item-1', name: 'Farmhouse Pizza', price: 350, restaurantId: 'rest-dominos' },
  { id: 'item-2', name: 'Peppy Paneer', price: 390, restaurantId: 'rest-dominos' },
  { id: 'item-3', name: 'Red Velvet Waffle', price: 140, restaurantId: 'rest-waffle' },
  { id: 'item-4', name: 'Triple Chocolate', price: 150, restaurantId: 'rest-waffle' },
  { id: 'item-5', name: 'Paneer Tikka Roll', price: 120, restaurantId: 'rest-chat' },
  { id: 'item-6', name: 'Aloo Tikki', price: 60, restaurantId: 'rest-chat' },
  { id: 'item-7', name: 'Double Cheese Pizza', price: 400, restaurantId: 'rest-uspizza' },
  { id: 'item-8', name: 'Mississippi Mud', price: 120, restaurantId: 'rest-br' },
  { id: 'item-9', name: 'Cotton Candy', price: 90, restaurantId: 'rest-br' },
];

export const BLOCK_COORDINATES = {
  A: { lat: 16.4619833645846, lon: 80.50799315633193 },
  B: { lat: 16.4630291, lon: 80.508394 },
  C: { lat: 16.460789852053995, lon: 80.50785908615744 },
} as const;

export const HOME_LOCATION: Coordinates = { lat: 16.463, lon: 80.5078 };

export const DELIVERY_LOCATIONS: DeliveryLocation[] = [
  { id: 'loc-a', name: 'SR Block & Ganga Hostel', location: BLOCK_COORDINATES.A },
  { id: 'loc-b', name: 'V Block', location: BLOCK_COORDINATES.B },
  { id: 'loc-c', name: 'C Block', location: BLOCK_COORDINATES.C },
];

const DRONE_HOME_1: Coordinates = HOME_LOCATION;
const DRONE_HOME_2: Coordinates = HOME_LOCATION;
const DRONE_HOME_3: Coordinates = HOME_LOCATION;


export const INITIAL_DRONES: Drone[] = [
  { id: 'D-01', model: 'Aero-1', status: DroneStatus.IDLE, battery: 98, location: DRONE_HOME_1, homeLocation: DRONE_HOME_1, isConnected: false, connectionString: 'udp:127.0.0.1:14550' },
  { id: 'D-02', model: 'Aero-1', status: DroneStatus.IDLE, battery: 100, location: DRONE_HOME_2, homeLocation: DRONE_HOME_2, isConnected: false, connectionString: 'udp:127.0.0.1:14551' },
  { id: 'D-03', model: 'Aero-2', status: DroneStatus.CHARGING, battery: 45, location: DRONE_HOME_3, homeLocation: DRONE_HOME_3, isConnected: false, connectionString: 'udp:127.0.0.1:14552' },
];

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
