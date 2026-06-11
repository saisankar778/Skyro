/**
 * useAppData.ts — Dynamic data hooks for Skyro frontend.
 *
 * All data (restaurants, menu items, delivery locations) is fetched from
 * the backend-orders API so it reflects the live AWS database.
 * No hardcoded data — add a restaurant in the DB and it appears here instantly.
 */

import { useState, useEffect, useCallback } from 'react';

const API_BASE = (import.meta.env.VITE_API_BASE as string) || 'http://127.0.0.1:8000';

// ─── Types (matching backend response shapes) ──────────────────────────────

export interface RestaurantData {
  id: string;
  name: string;
  tagline: string | null;
  rating: number;
  cuisine: string | null;
  delivery_time_min: number;
  price_for_two: number;
  offer: string | null;
  image_url: string | null;
  latitude: number;
  longitude: number;
  is_active: boolean;
}

export interface MenuItemData {
  id: string;
  restaurant_id: string;
  name: string;
  description: string | null;
  price: number;
  category: string | null;
  image_url: string | null;
  is_available: boolean;
}

export interface DeliveryLocationData {
  id: string;
  name: string;
  type: string;
  latitude: number;
  longitude: number;
  is_active: boolean;
}

// ─── Fallback data (shown while loading or if backend is unreachable) ──────

const RESTAURANT_FALLBACK: RestaurantData[] = [
  { id: 'Dominos',        name: "Domino's Pizza",  tagline: 'Hot & Fresh Pizzas',           rating: 4.3, cuisine: 'Pizza, Fast Food',  delivery_time_min: 20, price_for_two: 400, offer: '50% OFF',           image_url: 'https://images.unsplash.com/photo-1513104890138-7c749659a591?w=600&q=80', latitude: 16.463084574257913, longitude: 80.5084325541339,  is_active: true },
  { id: 'US_Pizza',       name: 'US Pizza',         tagline: 'American Style Gourmet Pizza', rating: 4.2, cuisine: 'Pizza, Italian',    delivery_time_min: 25, price_for_two: 500, offer: 'Buy 1 Get 1',        image_url: 'https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=600&q=80', latitude: 16.46277461846416,  longitude: 80.50822267128899, is_active: true },
  { id: 'Chat_and_Chill', name: 'Chat & Chill',     tagline: 'Street Food & Beverages',      rating: 4.5, cuisine: 'Street Food',       delivery_time_min: 10, price_for_two: 200, offer: 'Free Cold Drink',    image_url: 'https://images.unsplash.com/photo-1601050690597-df0568f70950?w=600&q=80', latitude: 16.462954675830282, longitude: 80.50807783200786, is_active: true },
  { id: 'Paradise',       name: 'Paradise',          tagline: 'Legendary Biryani & More',     rating: 4.7, cuisine: 'Biryani, Indian',   delivery_time_min: 20, price_for_two: 350, offer: 'Free Raita',         image_url: 'https://images.unsplash.com/photo-1563379091339-03b21ab4a4f8?w=600&q=80', latitude: 16.46286593329217,  longitude: 80.50807313814228, is_active: true },
  { id: 'Total_Fresh',    name: 'Total Fresh',       tagline: 'Healthy Juices & Fresh Meals', rating: 4.1, cuisine: 'Healthy, Juices',   delivery_time_min: 15, price_for_two: 180, offer: '15% OFF on combos',  image_url: 'https://images.unsplash.com/photo-1610970881699-44a5587cabec?w=600&q=80', latitude: 16.463118656500374, longitude: 80.50826089276595, is_active: true },
  { id: 'Baskin_Robins',  name: 'Baskin Robbins',    tagline: 'Premium Ice Cream Parlour',    rating: 4.4, cuisine: 'Ice Cream',         delivery_time_min: 12, price_for_two: 250, offer: '2 Scoops for 1',     image_url: 'https://images.unsplash.com/photo-1497034825429-c343d7c6a68f?w=600&q=80', latitude: 16.463022197299473, longitude: 80.50831923080973, is_active: true },
  { id: 'Nescafe',        name: 'Nescafe',           tagline: 'Your Perfect Cup Every Time',  rating: 4.0, cuisine: 'Coffee, Snacks',    delivery_time_min: 8,  price_for_two: 150, offer: 'Free Cookie',        image_url: 'https://images.unsplash.com/photo-1509042239860-f550ce710b93?w=600&q=80', latitude: 16.46288008065604,  longitude: 80.50844663573295, is_active: true },
];

const DELIVERY_FALLBACK: DeliveryLocationData[] = [
  { id: 'SR_Block',        name: 'SR Block',        type: 'DELIVERY_BLOCK', latitude: 16.462635294684286, longitude: 80.50647168669644, is_active: true },
  { id: 'C_Block',         name: 'C Block',         type: 'DELIVERY_BLOCK', latitude: 16.461646855350896, longitude: 80.50569336570064, is_active: true },
  { id: 'Admin_Block',     name: 'Admin Block',     type: 'DELIVERY_BLOCK', latitude: 16.464874583335895, longitude: 80.50791898212552, is_active: true },
  { id: 'Yamuna_Hostel',   name: 'Yamuna Hostel',   type: 'DELIVERY_BLOCK', latitude: 16.466254271237375, longitude: 80.50757917761362, is_active: true },
  { id: 'V_and_G_Hostels', name: 'V & G Hostels',  type: 'DELIVERY_BLOCK', latitude: 16.463886777402795, longitude: 80.50665800799868, is_active: true },
];

// ─── Hooks ──────────────────────────────────────────────────────────────────

/**
 * Fetches all active restaurants from the backend API.
 * Falls back to hardcoded data if the backend is unavailable.
 */
export function useRestaurants() {
  const [restaurants, setRestaurants] = useState<RestaurantData[]>(RESTAURANT_FALLBACK);
  const [loading, setLoading]         = useState(true);
  const [error, setError]             = useState<string | null>(null);

  const fetch_ = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/api/restaurants`, {
        headers: { 'ngrok-skip-browser-warning': 'true' }
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: RestaurantData[] = await res.json();
      if (data.length > 0) setRestaurants(data);
      setError(null);
    } catch (err: any) {
      console.warn('[useRestaurants] Falling back to hardcoded data:', err.message);
      setError(err.message);
      // Keep the fallback data already in state
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetch_(); }, [fetch_]);

  return { restaurants, loading, error, refetch: fetch_ };
}


/**
 * Fetches menu items, optionally for a specific restaurant.
 */
export function useMenuItems(restaurantId?: string) {
  const [menuItems, setMenuItems] = useState<MenuItemData[]>([]);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState<string | null>(null);

  const fetch_ = useCallback(async () => {
    try {
      setLoading(true);
      const qs  = restaurantId ? `?restaurant_id=${encodeURIComponent(restaurantId)}` : '';
      const res = await fetch(`${API_BASE}/api/menu-items${qs}`, {
        headers: { 'ngrok-skip-browser-warning': 'true' }
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: MenuItemData[] = await res.json();
      setMenuItems(data);
      setError(null);
    } catch (err: any) {
      console.warn('[useMenuItems] Failed to fetch menu items:', err.message);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [restaurantId]);

  useEffect(() => { fetch_(); }, [fetch_]);

  return { menuItems, loading, error, refetch: fetch_ };
}


/**
 * Fetches delivery locations (DELIVERY_BLOCK type) from the backend API.
 * Falls back to hardcoded GPS data if the backend is unavailable.
 */
export function useDeliveryLocations() {
  const [locations, setLocations] = useState<DeliveryLocationData[]>(DELIVERY_FALLBACK);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState<string | null>(null);

  const fetch_ = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/api/locations?type=DELIVERY_BLOCK`, {
        headers: { 'ngrok-skip-browser-warning': 'true' }
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: DeliveryLocationData[] = await res.json();
      if (data.length > 0) setLocations(data);
      setError(null);
    } catch (err: any) {
      console.warn('[useDeliveryLocations] Falling back to hardcoded data:', err.message);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetch_(); }, [fetch_]);

  return { locations, loading, error, refetch: fetch_ };
}
