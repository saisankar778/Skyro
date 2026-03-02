export enum OrderStatus {
  PLACED = 'Placed',
  DECLINED = 'Declined',
  ACCEPTED = 'Accepted',
  COOKING = 'Cooking',
  READY_FOR_LAUNCH = 'Ready for Launch',
  EN_ROUTE = 'En Route',
  DELIVERED = 'Delivered',
  FAILED = 'Failed',
}

export enum DroneStatus {
  IDLE = 'Idle',
  ON_MISSION = 'On Mission',
  RETURNING_HOME = 'Returning Home',
  CHARGING = 'Charging',
  MAINTENANCE = 'Maintenance',
}

export interface Coordinates {
  lat: number;
  lon: number;
}

export interface MenuItem {
  id: string;
  name: string;
  price: number;
  restaurantId: string;
}

export interface CartItem extends MenuItem {
  quantity: number;
}

export interface Order {
  id: string;
  user: string;
  restaurantId: string;
  items: CartItem[];
  total: number;
  deliveryLocationId: string;
  status: OrderStatus;
  createdAt: Date;
  droneId?: string;
}

export interface Drone {
  id: string;
  model: string;
  status: DroneStatus;
  battery: number;
  location: Coordinates;
  homeLocation: Coordinates;
  destination?: Coordinates;
  mission?: 'DELIVERY' | 'RETURN';
  isConnected: boolean;
  connectionString: string;
}

export interface Restaurant {
  id: string;
  name: string;
  location: Coordinates;
  rating?: number;
  deliveryTime?: string;
  cuisine?: string;
  priceForTwo?: number;
  offer?: string;
}

export interface DeliveryLocation {
  id: string;
  name: string;
  location: Coordinates;
}

export type NotificationType = 'info' | 'success' | 'warning' | 'error';

export interface Notification {
    id: number;
    message: string;
    type: NotificationType;
}
