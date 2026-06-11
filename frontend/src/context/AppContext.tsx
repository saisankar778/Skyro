import React, { createContext, useState, useCallback, ReactNode, FC, useEffect } from 'react';
import { Order, Drone, OrderStatus, DroneStatus, CartItem, Coordinates, Notification, NotificationType } from '@/types';
import { INITIAL_DRONES, HOME_LOCATIONS } from '@/constants';
import { useRestaurants, useMenuItems, useDeliveryLocations, RestaurantData, MenuItemData, DeliveryLocationData } from '@/hooks/useAppData';

type MapStyle = 'schematic' | 'satellite';

interface AppContextType {
  orders: Order[];
  drones: Drone[];
  restaurants: RestaurantData[];
  menuItems: MenuItemData[];
  deliveryLocations: DeliveryLocationData[];
  restaurantsLoading: boolean;
  menuItemsLoading: boolean;
  deliveryLocationsLoading: boolean;
  activityLog: string[];
  notifications: Notification[];
  mapStyle: MapStyle;
  placeOrder: (userId: string, cart: CartItem[], total: number, deliveryLocationId: string, restaurantId: string) => void;
  updateOrderStatus: (orderId: string, status: OrderStatus) => void;
  launchDroneForOrder: (orderId: string) => void;
  connectToDrone: (droneId: string) => void;
  disconnectFromDrone: (droneId: string) => void;
  commandRtl: (droneId: string) => void;
  removeNotification: (id: number) => void;
  updateDroneConnectionString: (droneId: string, value: string) => void;
  toggleMapStyle: () => void;
  addDrone: () => void;
}

export const AppContext = createContext<AppContextType | undefined>(undefined);

export const AppProvider: FC<{ children: ReactNode }> = ({ children }) => {
  const [orders, setOrders] = useState<Order[]>([]);
  const [drones, setDrones] = useState<Drone[]>(INITIAL_DRONES);
  const [activityLog, setActivityLog] = useState<string[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [mapStyle, setMapStyle] = useState<MapStyle>('schematic');

  // Live data from AWS DB via backend-orders API
  const { restaurants, loading: restaurantsLoading } = useRestaurants();
  const { menuItems, loading: menuItemsLoading } = useMenuItems();
  const { locations: deliveryLocations, loading: deliveryLocationsLoading } = useDeliveryLocations();

  // Backend API base (if not set, we keep in-memory behavior)
  const API_BASE = import.meta.env.VITE_API_BASE as string | undefined;
  const DRONE_API_BASE = import.meta.env.VITE_DRONE_API_BASE as string | undefined;
  const VARIANT = (import.meta.env.VITE_VARIANT as 'user' | 'vendor' | 'admin' | undefined);

  const getCurrentUserId = useCallback(() => {
    try {
      return localStorage.getItem('skyro_user') || undefined;
    } catch (_) {
      return undefined;
    }
  }, []);


  const logActivity = useCallback((message: string) => {
    const timestamp = new Date().toLocaleTimeString();
    setActivityLog(prev => [`[${timestamp}] ${message}`, ...prev].slice(0, 100));
  }, []);

  const removeNotification = (id: number) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
  };

  const addNotification = useCallback((message: string, type: NotificationType) => {
    setNotifications(prev => {
      // avoid duplicate notifications with the same message
      if (prev.some(n => n.message === message)) return prev;
      const id = Date.now();
      const next = [...prev, { id, message, type }];
      setTimeout(() => removeNotification(id), 5000);
      return next;
    });
  }, []);

  // --- Load existing orders from backend on app start ---
  useEffect(() => {
    if (!API_BASE) return;
    fetch(`${API_BASE}/api/orders`, {
      headers: { 'ngrok-skip-browser-warning': 'true' }
    })
      .then(res => {
        if (!res.ok) throw new Error(`Fetch orders failed: ${res.status}`);
        return res.json();
      })
      .then((data: any[]) => {
        const normalized: Order[] = data.map((o: any) => ({ ...o, createdAt: new Date(o.createdAt) }));
        setOrders(normalized);
        logActivity(`Loaded ${normalized.length} orders from server.`);
      })
      .catch(err => {
        console.error(err);
        addNotification('Failed to load orders from server.', 'error');
      });
  }, [API_BASE, addNotification, logActivity]);

  // --- Subscribe to realtime order events via WebSocket ---
  useEffect(() => {
    if (!API_BASE) return;
    const wsUrl = API_BASE.replace(/^http/, 'ws') + '/ws';
    const ws = new WebSocket(wsUrl);
    ws.onopen = () => logActivity('Connected to orders realtime feed.');
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg?.event === 'order_created' && msg.order) {
          const order: Order = { ...msg.order, createdAt: new Date(msg.order.createdAt) };
          setOrders(prev => [order, ...prev.filter(o => o.id !== order.id)]);
        } else if (msg?.event === 'order_updated' && msg.order) {
          const order: Order = { ...msg.order, createdAt: new Date(msg.order.createdAt) };
          setOrders(prev => {
            const prevOrder = prev.find(o => o.id === order.id);
            const becameDelivered = order.status === OrderStatus.DELIVERED && prevOrder?.status !== OrderStatus.DELIVERED;
            const isUserView = VARIANT === 'user';
            const shouldNotify = becameDelivered && (isUserView ? order.user === getCurrentUserId() : true);
            if (shouldNotify) {
              const msgText = isUserView ? `Your order ${order.id} has been delivered.` : `Order ${order.id} has been delivered.`;
              addNotification(msgText, 'success');
            }
            return prev.map(o => o.id === order.id ? order : o);
          });
        }
      } catch (_) {
        // ignore parse errors
      }
    };
    ws.onclose = () => logActivity('Disconnected from orders realtime feed.');
    return () => ws.close();
  }, [API_BASE, VARIANT, addNotification, getCurrentUserId, logActivity]);

  const placeOrder = useCallback((userId: string, cart: CartItem[], total: number, deliveryLocationId: string, restaurantId: string) => {
    if (!API_BASE) {
      // Fallback to in-memory behavior if backend is not configured
      const newOrder: Order = {
        id: `ORD-${Date.now()}`,
        user: userId,
        restaurantId,
        items: cart,
        total,
        deliveryLocationId,
        status: OrderStatus.PLACED,
        createdAt: new Date(),
      };
      setOrders(prev => [newOrder, ...prev]);
      logActivity(`New order ${newOrder.id} placed.`);
      return;
    }

    // Resolve deliveryLocationId: the frontend might use a name-based ID (e.g. 'SR_Block')
    // but the DB stores UUID primary keys. Try to find the matching DB location UUID.
    const dbLocation = deliveryLocations.find(
      l => l.id === deliveryLocationId || l.name === deliveryLocationId ||
        l.name.replace(/\s+/g, '_') === deliveryLocationId ||
        l.id.replace(/\s+/g, '_') === deliveryLocationId
    );
    const resolvedLocationId = dbLocation?.id ?? deliveryLocationId;

    const body = {
      user: userId,
      restaurantId,
      items: cart,
      total,
      deliveryLocationId: resolvedLocationId,
      status: OrderStatus.PLACED,
    };
    fetch(`${API_BASE}/api/orders`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'ngrok-skip-browser-warning': 'true'
      },
      body: JSON.stringify(body),
    })
      .then(res => {
        if (!res.ok) throw new Error(`Place order failed: ${res.status}`);
        return res.json();
      })
      .then((created) => {
        logActivity(`New order ${created.id} placed.`);
        // Rely on WS broadcast to add order; as a fallback, add it now
        setOrders(prev => [{ ...created, createdAt: new Date(created.createdAt) }, ...prev]);
      })
      .catch(err => {
        addNotification(`Failed to place order: ${err.message}`, 'error');
      });
  }, [API_BASE, deliveryLocations, addNotification, logActivity]);

  const updateOrderStatus = useCallback((orderId: string, status: OrderStatus) => {
    // Helper to apply status change locally and emit notifications
    const applyStatusLocally = (newStatus: OrderStatus) => {
      setOrders(prev =>
        prev.map(order =>
          order.id === orderId ? { ...order, status: newStatus } : order
        )
      );
      if (newStatus === OrderStatus.ACCEPTED) {
        addNotification(`Order ${orderId} accepted by the restaurant!`, 'success');
      } else if (newStatus === OrderStatus.COOKING) {
        addNotification(`Order ${orderId} is now being prepared!`, 'info');
      } else if (newStatus === OrderStatus.READY_FOR_LAUNCH) {
        addNotification(`Order ${orderId} is ready for launch!`, 'info');
      } else if (newStatus === OrderStatus.DECLINED) {
        addNotification(`Order ${orderId} was declined.`, 'error');
      } else if (newStatus === OrderStatus.FAILED) {
        addNotification(`Order ${orderId} has been cancelled.`, 'warning');
      } else if (newStatus === OrderStatus.DELIVERED) {
        const isUserView = VARIANT === 'user';
        addNotification(isUserView ? `Your order ${orderId} has been delivered!` : `Order ${orderId} has been delivered.`, 'success');
      }
      logActivity(`Order ${orderId} status updated to ${newStatus}.`);
    };

    if (!API_BASE) {
      applyStatusLocally(status);
      return;
    }
    fetch(`${API_BASE}/api/orders/${orderId}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        'ngrok-skip-browser-warning': 'true'
      },
      body: JSON.stringify({ status }),
    })
      .then(res => {
        if (!res.ok) throw new Error(`Update failed: ${res.status}`);
        return res.json();
      })
      .then((updatedOrder) => {
        // Optimistically apply the update immediately — don't wait for WS
        const serverStatus = (updatedOrder?.status as OrderStatus) || status;
        applyStatusLocally(serverStatus);
      })
      .catch(err => {
        addNotification(`Failed to update order ${orderId}: ${err.message}`, 'error');
      });
  }, [API_BASE, VARIANT, addNotification, logActivity]);

  const launchDroneForOrder = useCallback((orderId: string) => {
    const order = orders.find(o => o.id === orderId);
    if (!order) return;

    // Resolve delivery location — the order may store a name-based ID ('SR_Block'),
    // a DB UUID, or a display name. We need both GPS coords (for the map) and the
    // backend BLOCK_COORDINATES key (to send to the drone backend).
    const VALID_BLOCK_NAMES = ['SR_Block', 'C_Block', 'Admin_Block', 'Yamuna_Hostel', 'V_and_G_Hostels'];
    const locId = order.deliveryLocationId;

    // 1. If it's already a valid block name, use it directly
    let blockName: string | null = VALID_BLOCK_NAMES.includes(locId) ? locId : null;
    let deliveryLocation = deliveryLocations.find(l => l.id === locId);

    // 2. If not found by exact ID, check DB locations by name or name-to-underscore match
    if (!deliveryLocation) {
      deliveryLocation = deliveryLocations.find(
        l => l.name === locId ||
          l.name.replace(/\s+/g, '_') === locId ||
          l.id === locId
      );
    }

    // 3. Derive block name from DB location name if we don't have it yet
    if (!blockName && deliveryLocation) {
      const normalized = deliveryLocation.name.replace(/\s+/g, '_').replace(/&/g, 'and');
      blockName = VALID_BLOCK_NAMES.find(b => b === normalized || b === deliveryLocation!.name) ?? null;
      // Try partial match as last resort
      if (!blockName) {
        blockName = VALID_BLOCK_NAMES.find(b =>
          b.toLowerCase().includes(normalized.toLowerCase()) ||
          normalized.toLowerCase().includes(b.toLowerCase())
        ) ?? null;
      }
    }

    if (!blockName) {
      const msg = `Cannot resolve block for order ${orderId} (location: ${locId}). Valid blocks: ${VALID_BLOCK_NAMES.join(', ')}.`;
      logActivity(msg);
      addNotification(msg, 'error');
      updateOrderStatus(orderId, OrderStatus.FAILED);
      return;
    }

    // GPS coords for UI map — fall back to hardcoded if DB didn't return coords
    const gpsCoords = deliveryLocation
      ? { lat: deliveryLocation.latitude, lon: deliveryLocation.longitude }
      : (() => {
        const { BLOCK_COORDINATES } = {
          BLOCK_COORDINATES: {
            SR_Block: { lat: 16.462635294684286, lon: 80.50647168669644 },
            C_Block: { lat: 16.461646855350896, lon: 80.50569336570064 },
            Admin_Block: { lat: 16.464874583335895, lon: 80.50791898212552 },
            Yamuna_Hostel: { lat: 16.466254271237375, lon: 80.50757917761362 },
            V_and_G_Hostels: { lat: 16.463886777402795, lon: 80.50665800799868 },
          }
        };
        return (BLOCK_COORDINATES as Record<string, { lat: number, lon: number }>)[blockName!] ?? { lat: 0, lon: 0 };
      })();
    // --- Trigger backend drone automation ---
    const backendUrl = `${(DRONE_API_BASE || 'http://127.0.0.1:8080')}/api/launch`;
    logActivity(`Sending launch command to backend for order ${orderId} (block '${blockName}')...`);

    fetch(backendUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'ngrok-skip-browser-warning': 'true'
      },
      body: JSON.stringify({
        drone_id: "",
        order_id: orderId,
        delivery_lat: gpsCoords.lat,
        delivery_lon: gpsCoords.lon,
        delivery_alt: 20.0
      }),
    })
      .then(response => {
        if (!response.ok) {
          return response.json().then(err => {
            throw new Error(err.message || `Backend error: ${response.status}`);
          }).catch(() => {
            throw new Error(`Backend error: ${response.status}`);
          });
        }
        return response.json();
      })
      .then(data => {
        // The backend assigns a drone — extract the drone_id from the response
        const assignedDroneId: string = data.drone_id || data.droneId || '';
        logActivity(`Backend accepted mission for order ${orderId}. Drone: ${assignedDroneId || 'assigning…'}`);

        // Update order status to EN_ROUTE
        setOrders(prev =>
          prev.map(o =>
            o.id === orderId
              ? { ...o, status: OrderStatus.EN_ROUTE, droneId: assignedDroneId || o.droneId }
              : o
          )
        );

        // If we know the assigned drone, reflect it immediately in the drone list
        if (assignedDroneId) {
          setDrones(prev =>
            prev.map(d =>
              d.id === assignedDroneId
                ? { ...d, status: DroneStatus.ON_MISSION, mission: 'DELIVERY', destination: gpsCoords }
                : d
            )
          );
        }

        // Persist EN_ROUTE status to orders backend so other clients see the map
        if (API_BASE) {
          fetch(`${API_BASE}/api/orders/${orderId}`, {
            method: 'PATCH',
            headers: {
              'Content-Type': 'application/json',
              'ngrok-skip-browser-warning': 'true'
            },
            body: JSON.stringify({ status: OrderStatus.EN_ROUTE, droneId: assignedDroneId }),
          }).catch(() => {/* noop — WS will keep others updated */ });
        }

        logActivity(`Drone ${assignedDroneId || '(assigning)'} launched for order ${orderId}.`);
        addNotification(`Drone launched for your order ${orderId}!`, 'info');

        setTimeout(() => logActivity(`Arming motors…`), 1000);
        setTimeout(() => logActivity(`Taking off for delivery.`), 3000);
      })
      .catch(error => {
        const errorMsg = `Failed to send launch command for order ${orderId}: ${error.message}`;
        logActivity(errorMsg);
        addNotification(`Mission start failed: ${error.message}`, 'error');
        updateOrderStatus(orderId, OrderStatus.FAILED);
      });

  }, [orders, deliveryLocations, updateOrderStatus, addNotification, logActivity, DRONE_API_BASE, API_BASE]);

  const connectToDrone = (droneId: string) => {
    const drone = drones.find(d => d.id === droneId);
    if (!drone) return;

    logActivity(`Attempting to connect to drone ${droneId} at ${drone.connectionString}...`);

    // Call backend to establish real connection
    const backendUrl = `${(DRONE_API_BASE || 'http://127.0.0.1:8080')}/api/connect`;

    fetch(backendUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'ngrok-skip-browser-warning': 'true'
      },
      body: JSON.stringify({
        drone_id: droneId,
        connection_string: drone.connectionString
      }),
    })
      .then(response => {
        console.log('Response status:', response.status);
        if (response.ok) {
          return response.json();
        } else {
          // FastAPI returns JSON error messages
          return response.json().then(err => {
            console.log('FastAPI error response:', err);
            throw new Error(err.detail || `Backend connection failed: ${response.status}`);
          }).catch((parseError) => {
            console.error('Error parsing response:', parseError);
            throw new Error(`Backend connection failed: ${response.status}`);
          });
        }
      })
      .then(data => {
        logActivity(`Successfully connected to drone ${droneId}. ${data.status}`);
        setDrones(prev => prev.map(d => d.id === droneId ? {
          ...d,
          isConnected: true,
          status: DroneStatus.IDLE // Start as idle when connected
        } : d));
        addNotification(`Drone ${droneId} connected successfully!`, 'success');
      })
      .catch(error => {
        logActivity(`Failed to connect to drone ${droneId}: ${error.message}`);
        addNotification(`Connection failed: ${error.message}`, 'error');
      });
  };

  const disconnectFromDrone = (droneId: string) => {
    const drone = drones.find(d => d.id === droneId);
    if (!drone) return;
    logActivity(`Disconnecting from drone ${droneId}...`);
    const backendUrl = `${(DRONE_API_BASE || 'http://127.0.0.1:8080')}/api/drones/${droneId}`;
    fetch(backendUrl, {
      method: 'DELETE',
      headers: { 'ngrok-skip-browser-warning': 'true' }
    })
      .then(res => {
        if (res.ok) return res.json();
        return res.json().then(err => {
          throw new Error(err.detail || `Backend disconnect failed: ${res.status}`);
        }).catch(() => { throw new Error(`Backend disconnect failed: ${res.status}`); });
      })
      .then(() => {
        setDrones(prev => prev.map(d => d.id === droneId ? { ...d, isConnected: false, status: d.status === DroneStatus.ON_MISSION ? d.status : DroneStatus.IDLE } : d));
        addNotification(`Drone ${droneId} disconnected.`, 'info');
        logActivity(`Drone ${droneId} disconnected.`);
      })
      .catch(error => {
        addNotification(`Failed to disconnect drone ${droneId}: ${error.message}`, 'error');
        logActivity(`Failed to disconnect drone ${droneId}: ${error.message}`);
      });
  };

  const updateDroneConnectionString = (droneId: string, value: string) => {
    setDrones(prev => prev.map(d => d.id === droneId ? { ...d, connectionString: value } : d));
  };

  const commandRtl = (droneId: string) => {
    const drone = drones.find(d => d.id === droneId);
    if (!drone || !drone.isConnected) {
      logActivity(`Cannot send RTL: Drone ${droneId} not connected.`);
      return;
    }
    if (drone.status === DroneStatus.ON_MISSION) {
      logActivity(`Commanding drone ${droneId} to Return to Launch.`);
      setDrones(prev => prev.map(d =>
        d.id === droneId ? { ...d, status: DroneStatus.RETURNING_HOME, mission: 'RETURN', destination: d.homeLocation } : d
      ));
      const order = orders.find(o => o.droneId === droneId && o.status === OrderStatus.EN_ROUTE);
      if (order) {
        updateOrderStatus(order.id, OrderStatus.FAILED);
        logActivity(`Order ${order.id} failed due to manual RTL.`);
        addNotification(`Delivery for order ${order.id} was cancelled.`, 'warning');
      }
    } else {
      logActivity(`Drone ${droneId} is not on a delivery mission, RTL command ignored.`);
    }
  };

  const toggleMapStyle = () => {
    setMapStyle(prev => prev === 'schematic' ? 'satellite' : 'schematic');
  }

  const addDrone = useCallback(() => {
    setDrones(prev => {
      const nextIndex = prev.length;
      const nextIdNumber = nextIndex + 1;
      const id = `D-${nextIdNumber.toString().padStart(2, '0')}`;
      
      // Calculate port: 14551 + index * 110 (D-01 is 14551, D-02 is 14661, D-03 is 14771, etc.)
      const port = 14551 + nextIndex * 110;
      const connectionString = `udp:127.0.0.1:${port}`;
      
      const homeLoc = HOME_LOCATIONS[nextIndex % HOME_LOCATIONS.length];
      
      const newDrone = {
        id,
        model: 'Aero-1',
        status: DroneStatus.IDLE,
        battery: 100,
        location: homeLoc,
        homeLocation: homeLoc,
        isConnected: false,
        connectionString,
      };
      
      logActivity(`Added new drone ${id} to inventory list.`);
      return [...prev, newDrone];
    });
  }, [logActivity]);


  useEffect(() => {
    // When a real backend is configured, disable local simulation
    if (API_BASE) return;
    const simulationInterval = setInterval(() => {
      setDrones(currentDrones => {
        return currentDrones.map(drone => {
          if ((drone.status === DroneStatus.ON_MISSION || drone.status === DroneStatus.RETURNING_HOME) && drone.destination) {
            const { location, destination } = drone;
            const distLat = destination.lat - location.lat;
            const distLon = destination.lon - location.lon;
            const distance = Math.sqrt(distLat ** 2 + distLon ** 2);

            if (distance < 0.0001) {
              if (drone.mission === 'DELIVERY') {
                const order = orders.find(o => o.droneId === drone.id && o.status === OrderStatus.EN_ROUTE);
                if (order) {
                  const locName = deliveryLocations.find(l => l.id === order.deliveryLocationId)?.name;
                  logActivity(`[${drone.id}] Arrived at ${locName}.`);
                  addNotification(`Your order ${order.id} has arrived!`, 'success');
                  setTimeout(() => logActivity(`[${drone.id}] Releasing payload...`), 1000);
                  setTimeout(() => {
                    logActivity(`[${drone.id}] Payload released. Returning to launch.`);
                    updateOrderStatus(order.id, OrderStatus.DELIVERED);
                    return setDrones(prev => prev.map(d => d.id === drone.id ? { ...d, status: DroneStatus.RETURNING_HOME, mission: 'RETURN', destination: d.homeLocation } : d));
                  }, 2500);
                }
              } else if (drone.mission === 'RETURN') {
                logActivity(`[${drone.id}] Returned to home base. Landing.`);
                return { ...drone, status: DroneStatus.IDLE, mission: undefined, destination: undefined, location: drone.homeLocation };
              }
              return drone;
            }

            const speed = drone.mission === 'DELIVERY' ? 0.0003 : 0.0005;
            const moveLat = (distLat / distance) * speed;
            const moveLon = (distLon / distance) * speed;

            return { ...drone, location: { lat: location.lat + moveLat, lon: location.lon + moveLon } };
          }
          return drone;
        });
      });
    }, 100);

    return () => clearInterval(simulationInterval);
  }, [orders, addNotification, updateOrderStatus, logActivity, API_BASE]);

  // Real-time status updates for connected drones — fetched globally from backend to sync across tabs/devices
  useEffect(() => {
    const fetchStatus = () => {
      const droneUrl = DRONE_API_BASE || 'http://127.0.0.1:8080';
      fetch(`${droneUrl}/api/drones/status`, {
        headers: { 'ngrok-skip-browser-warning': 'true' }
      })
        .then(res => {
          if (!res.ok) throw new Error(`Status check failed: ${res.status}`);
          return res.json();
        })
        .then((data: Record<string, any>) => {
          const remoteDrones: Record<string, any> = data.drones || {};
          setDrones(prev => {
            const existingIds = new Set(prev.map(d => d.id));

            // Map the status string from backend to our DroneStatus enum
            const mapStatus = (remote: any): DroneStatus => {
              if (remote.status === 'RETURNING_HOME') return DroneStatus.RETURNING_HOME;
              if (remote.status === 'CHARGING') return DroneStatus.CHARGING;
              if (remote.status === 'MAINTENANCE' || remote.status === 'FAILED') return DroneStatus.MAINTENANCE;
              if (remote.status === 'IN_FLIGHT' || remote.status === 'LANDING' || remote.status === 'CONNECTING') return DroneStatus.ON_MISSION;
              return remote.armed ? DroneStatus.ON_MISSION : DroneStatus.IDLE;
            };

            // Update existing drones
            const updated = prev.map(d => {
              const remote = remoteDrones[d.id];
              if (remote) {
                return {
                  ...d,
                  isConnected: remote.status !== 'OFFLINE' && remote.is_online !== false,
                  status: mapStatus(remote),
                  battery: typeof remote.battery === 'number' ? remote.battery : d.battery,
                  location: remote.location?.lat && remote.location?.lon ? { lat: remote.location.lat, lon: remote.location.lon } : d.location,
                  destination: remote.destination?.lat && remote.destination?.lon ? { lat: remote.destination.lat, lon: remote.destination.lon } : d.destination,
                  homeLocation: remote.home_location?.lat && remote.home_location?.lon ? { lat: remote.home_location.lat, lon: remote.home_location.lon } : d.homeLocation,
                };
              }
              // Drone not in backend status response — mark disconnected
              return { ...d, isConnected: false };
            });

            // Add brand-new drones from backend that weren’t in INITIAL_DRONES
            const newDrones = Object.entries(remoteDrones)
              .filter(([id]) => !existingIds.has(id) && (remoteDrones[id].status !== 'OFFLINE'))
              .map(([id, remote]: [string, any]) => ({
                id,
                model: remote.model || 'Unknown',
                status: mapStatus(remote),
                battery: typeof remote.battery === 'number' ? remote.battery : 0,
                location: remote.location?.lat && remote.location?.lon
                  ? { lat: remote.location.lat, lon: remote.location.lon }
                  : { lat: 16.4628, lon: 80.5073 },
                homeLocation: remote.home_location?.lat && remote.home_location?.lon
                  ? { lat: remote.home_location.lat, lon: remote.home_location.lon }
                  : { lat: 16.4628, lon: 80.5073 },
                destination: remote.destination?.lat && remote.destination?.lon
                  ? { lat: remote.destination.lat, lon: remote.destination.lon }
                  : undefined,
                isConnected: true,
                connectionString: remote.connection_string || '',
              } as any));

            return [...updated, ...newDrones];
          });
        })
        .catch(err => {
          console.warn('Failed to poll drone status from backend:', err);
        });
    };

    fetchStatus();
    const statusInterval = setInterval(fetchStatus, 5000);
    return () => clearInterval(statusInterval);
  }, [DRONE_API_BASE]);

  // WebSocket: subscribe to live drone status for smoother map updates
  useEffect(() => {
    const wsBase = (DRONE_API_BASE || 'http://127.0.0.1:8080').replace(/^http/, 'ws');
    const ws = new WebSocket(`${wsBase}/ws`);
    ws.onopen = () => logActivity('Connected to drone status WebSocket.');
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg?.type === 'status_update' && msg.drones) {
          setDrones(prev => {
            const existingIds = new Set(prev.map(d => d.id));

            const mapStatus = (data: any): DroneStatus => {
              if (data.status === 'RETURNING_HOME') return DroneStatus.RETURNING_HOME;
              if (data.status === 'CHARGING') return DroneStatus.CHARGING;
              if (data.status === 'MAINTENANCE' || data.status === 'FAILED') return DroneStatus.MAINTENANCE;
              if (data.status === 'IN_FLIGHT' || data.status === 'LANDING' || data.status === 'CONNECTING') return DroneStatus.ON_MISSION;
              return data.armed ? DroneStatus.ON_MISSION : DroneStatus.IDLE;
            };

            const next = prev.map(d => {
              const data: any = msg.drones[d.id];
              if (!data) return d;
              return {
                ...d,
                status: mapStatus(data),
                battery: typeof data.battery === 'number' ? data.battery : d.battery,
                isConnected: data.status !== 'OFFLINE' && data.is_online !== false,
                location: data.location?.lat && data.location?.lon
                  ? { lat: data.location.lat, lon: data.location.lon }
                  : d.location,
                destination: data.destination?.lat && data.destination?.lon
                  ? { lat: data.destination.lat, lon: data.destination.lon }
                  : d.destination,
                homeLocation: data.home_location?.lat && data.home_location?.lon
                  ? { lat: data.home_location.lat, lon: data.home_location.lon }
                  : d.homeLocation,
              };
            });

            // Merge in backend drones not in INITIAL_DRONES
            const newDrones = Object.entries<any>(msg.drones)
              .filter(([id, data]) => !existingIds.has(id) && data.status !== 'OFFLINE')
              .map(([id, data]: [string, any]) => ({
                id,
                model: data.model || 'Unknown',
                status: mapStatus(data),
                battery: typeof data.battery === 'number' ? data.battery : 0,
                location: data.location?.lat && data.location?.lon
                  ? { lat: data.location.lat, lon: data.location.lon }
                  : { lat: 16.4628, lon: 80.5073 },
                homeLocation: data.home_location?.lat && data.home_location?.lon
                  ? { lat: data.home_location.lat, lon: data.home_location.lon }
                  : { lat: 16.4628, lon: 80.5073 },
                destination: data.destination?.lat && data.destination?.lon
                  ? { lat: data.destination.lat, lon: data.destination.lon }
                  : undefined,
                isConnected: true,
                connectionString: data.connection_string || '',
              } as any));

            return [...next, ...newDrones];
          });
        }
      } catch (_) {
        // ignore parse errors
      }
    };
    ws.onclose = () => logActivity('Drone status WebSocket closed.');
    return () => ws.close();
  }, [logActivity, DRONE_API_BASE]);


  return (
    <AppContext.Provider value={{
      orders, drones,
      restaurants, menuItems, deliveryLocations,
      restaurantsLoading, menuItemsLoading, deliveryLocationsLoading,
      activityLog, notifications, mapStyle,
      placeOrder, updateOrderStatus, launchDroneForOrder,
      connectToDrone, disconnectFromDrone, commandRtl,
      removeNotification, updateDroneConnectionString, toggleMapStyle, addDrone
    }}>
      {children}
    </AppContext.Provider>
  );
};