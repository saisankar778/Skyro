import React, { createContext, useState, useCallback, ReactNode, FC, useEffect } from 'react';
import { Order, Drone, OrderStatus, DroneStatus, CartItem, Coordinates, Notification, NotificationType } from '@/types';
import { INITIAL_DRONES, DELIVERY_LOCATIONS, RESTAURANTS } from '@/constants';

type MapStyle = 'schematic' | 'satellite';

interface AppContextType {
  orders: Order[];
  drones: Drone[];
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
}

export const AppContext = createContext<AppContextType | undefined>(undefined);

export const AppProvider: FC<{children: ReactNode}> = ({ children }) => {
  const [orders, setOrders] = useState<Order[]>([]);
  const [drones, setDrones] = useState<Drone[]>(INITIAL_DRONES);
  const [activityLog, setActivityLog] = useState<string[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [mapStyle, setMapStyle] = useState<MapStyle>('schematic');

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
    fetch(`${API_BASE}/api/orders`)
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
    const body = {
      user: userId,
      restaurantId,
      items: cart,
      total,
      deliveryLocationId,
      status: OrderStatus.PLACED,
    };
    fetch(`${API_BASE}/api/orders`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
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
  }, [API_BASE, addNotification, logActivity]);

  const updateOrderStatus = useCallback((orderId: string, status: OrderStatus) => {
    if (!API_BASE) {
      // Fallback to in-memory behavior
      setOrders(prev =>
        prev.map(order => {
          if (order.id === orderId && order.status !== status) {
              if (status === OrderStatus.ACCEPTED) {
                  addNotification(`Order ${orderId} has been accepted by the restaurant!`, 'success');
              } else if (status === OrderStatus.DECLINED) {
                  addNotification(`Order ${orderId} was declined.`, 'error');
              } else if (status === OrderStatus.DELIVERED) {
                  const isUserView = VARIANT === 'user';
                  addNotification(isUserView ? `Your order ${orderId} has been delivered.` : `Order ${orderId} has been delivered.`, 'success');
              }
               return { ...order, status };
          }
          return order;
        })
      );
      logActivity(`Order ${orderId} status updated to ${status}.`);
      return;
    }
    fetch(`${API_BASE}/api/orders/${orderId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    })
      .then(res => {
        if (!res.ok) throw new Error(`Update failed: ${res.status}`);
        return res.json();
      })
      .then(() => {
        if (status === OrderStatus.ACCEPTED) {
          addNotification(`Order ${orderId} has been accepted by the restaurant!`, 'success');
        } else if (status === OrderStatus.DECLINED) {
          addNotification(`Order ${orderId} was declined.`, 'error');
        } else if (status === OrderStatus.DELIVERED) {
          const isUserView = VARIANT === 'user';
          addNotification(isUserView ? `Your order ${orderId} has been delivered.` : `Order ${orderId} has been delivered.`, 'success');
        }
        logActivity(`Order ${orderId} status updated to ${status}.`);
        // No local state change here; realtime WS will update. As a safety, we could optimistically update if needed.
      })
      .catch(err => {
        addNotification(`Failed to update order ${orderId}: ${err.message}`, 'error');
      });
  }, [API_BASE, addNotification, logActivity]);
  
  const launchDroneForOrder = useCallback((orderId: string) => {
    const order = orders.find(o => o.id === orderId);
    if (!order) return;

    const availableDrone = drones.find(d => d.status === DroneStatus.IDLE && d.isConnected);
    if (!availableDrone) {
      const msg = `No connected and idle drones available for order ${orderId}.`;
      logActivity(msg);
      addNotification(msg, 'warning');
      updateOrderStatus(orderId, OrderStatus.FAILED);
      return;
    }
    
    const deliveryLocation = DELIVERY_LOCATIONS.find(l => l.id === order.deliveryLocationId);
    if (!deliveryLocation) {
        const msg = `Delivery location for order ${orderId} not found.`;
        logActivity(msg);
        addNotification(msg, 'error');
        updateOrderStatus(orderId, OrderStatus.FAILED);
        return;
    }

    // --- Trigger backend drone automation ---
    const backendUrl = `${(DRONE_API_BASE || 'http://127.0.0.1:8080')}/api/launch`;
    logActivity(`[${availableDrone.id}] Sending launch command to backend...`);
    
    // Map delivery location to block (A, B, or C)
    const blockMap: { [key: string]: string } = {
      'loc-a': 'A',
      'loc-b': 'B', 
      'loc-c': 'C'
    };
    const block = blockMap[order.deliveryLocationId] || 'A';
    
    fetch(backendUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            droneId: availableDrone.id,
            connectionString: availableDrone.connectionString,
            block: block,
            orderId: orderId,
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
        logActivity(`[${availableDrone.id}] Backend accepted mission: ${data.status}`);
        
        // Immediately reflect mission start in UI so the map appears and path renders
        setDrones(prev =>
          prev.map(d =>
            d.id === availableDrone.id ? { ...d, status: DroneStatus.ON_MISSION, mission: 'DELIVERY', destination: deliveryLocation.location } : d
          )
        );
        setOrders(prev =>
          prev.map(o =>
            o.id === orderId ? { ...o, status: OrderStatus.EN_ROUTE, droneId: availableDrone.id } : o
          )
        );

        // Persist EN_ROUTE status to orders backend so other clients (e.g., User UI) see the map
        if (API_BASE) {
          fetch(`${API_BASE}/api/orders/${orderId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: OrderStatus.EN_ROUTE, droneId: availableDrone.id }),
          }).catch(() => {/* noop: WS will keep others updated; local UI already updated */});
        }

        logActivity(`Drone ${availableDrone.id} assigned to order ${orderId}.`);
        addNotification(`Drone launched for your order ${orderId}!`, 'info');

        // Keep staged logs for realism
        setTimeout(() => {
            logActivity(`[${availableDrone.id}] Arming motors...`);
        }, 1000);
        setTimeout(() => {
            logActivity(`[${availableDrone.id}] Taking off for delivery.`);
        }, 3000);
    })
    .catch(error => {
        const errorMsg = `Failed to send command to backend for drone ${availableDrone.id}. ${error.message}`;
        logActivity(errorMsg);
        addNotification(`Mission start failed: ${error.message}`, 'error');
        updateOrderStatus(orderId, OrderStatus.FAILED);
    });

  }, [orders, drones, updateOrderStatus, addNotification, logActivity]);

  const connectToDrone = (droneId: string) => {
    const drone = drones.find(d => d.id === droneId);
    if (!drone) return;
    
    logActivity(`Attempting to connect to drone ${droneId} at ${drone.connectionString}...`);
    
    // Call backend to establish real connection
    const backendUrl = `${(DRONE_API_BASE || 'http://127.0.0.1:8080')}/api/connect`;
    
    fetch(backendUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            droneId: droneId,
            connectionString: drone.connectionString,
            block: 'A' // Required field, but not used for connection
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

  useEffect(() => {
    // When a real backend is configured, disable local simulation to avoid premature Delivered updates
    if (API_BASE) return;
    const simulationInterval = setInterval(() => {
        setDrones(currentDrones => {
            return currentDrones.map(drone => {
                if ((drone.status === DroneStatus.ON_MISSION || drone.status === DroneStatus.RETURNING_HOME) && drone.destination) {
                    const { location, destination } = drone;
                    const distLat = destination.lat - location.lat;
                    const distLon = destination.lon - location.lon;
                    const distance = Math.sqrt(distLat**2 + distLon**2);

                    if (distance < 0.0001) {
                        if (drone.mission === 'DELIVERY') {
                            const order = orders.find(o => o.droneId === drone.id && o.status === OrderStatus.EN_ROUTE);
                            if (order) {
                                logActivity(`[${drone.id}] Arrived at ${DELIVERY_LOCATIONS.find(l => l.id === order.deliveryLocationId)?.name}.`);
                                addNotification(`Your order ${order.id} has arrived!`, 'success');
                                setTimeout(() => logActivity(`[${drone.id}] Releasing payload...`), 1000);
                                setTimeout(() => {
                                    logActivity(`[${drone.id}] Payload released. Returning to launch.`);
                                    // In simulation mode, mark delivered locally. Real mode will be updated by backend-orders.
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

  // Real-time status updates for connected drones
  useEffect(() => {
    const statusInterval = setInterval(() => {
        drones.forEach(drone => {
            if (drone.isConnected) {
                fetch(`${(DRONE_API_BASE || 'http://127.0.0.1:8080')}/api/status`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ droneId: drone.id }),
                })
                .then(response => {
                    if (response.ok) {
                        return response.json();
                    } else {
                        // FastAPI returns JSON error messages
                        return response.json().then(err => {
                            console.log('Status check error:', err);
                            throw new Error(err.detail || `Status check failed: ${response.status}`);
                        }).catch((parseError) => {
                            console.error('Status check parse error:', parseError);
                            throw new Error(`Status check failed: ${response.status}`);
                        });
                    }
                })
                .then(data => {
                    setDrones(prev => prev.map(d => 
                        d.id === drone.id ? { 
                            ...d, 
                            status: data.armed ? DroneStatus.ON_MISSION : DroneStatus.IDLE,
                            battery: data.battery || d.battery, // Use real battery data only
                            // Update location with real GPS data from drone only if valid
                            location: data.location && data.location.lat !== 0 && data.location.lon !== 0 ? {
                                lat: data.location.lat,
                                lon: data.location.lon
                            } : d.location
                        } : d
                    ));
                    
                    // Do not auto-mark Delivered on the client; rely on backend-orders to update status
                    // We may still log proximity/landing events here if desired.
                })
                .catch(() => {
                    // Connection lost - mark as disconnected
                    setDrones(prev => prev.map(d => 
                        d.id === drone.id ? { ...d, isConnected: false } : d
                    ));
                });
            }
        });
    }, 2000); // Check every 2 seconds for more responsive updates

    return () => clearInterval(statusInterval);
  }, [drones, orders, addNotification, logActivity]);

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
            const next = [...prev];
            Object.entries<any>(msg.drones).forEach(([droneId, data]) => {
              const idx = next.findIndex(d => d.id === droneId);
              if (idx !== -1) {
                const d = next[idx];
                next[idx] = {
                  ...d,
                  status: data.armed ? DroneStatus.ON_MISSION : DroneStatus.IDLE,
                  battery: typeof data.battery === 'number' ? data.battery : d.battery,
                  isConnected: true,
                  location: data.location && data.location.lat && data.location.lon ? {
                    lat: data.location.lat,
                    lon: data.location.lon,
                  } : d.location,
                };
              }
            });
            return next;
          });
        }
      } catch (_) {
        // ignore parse errors
      }
    };
    ws.onclose = () => logActivity('Drone status WebSocket closed.');
    return () => ws.close();
  }, [logActivity]);


  return (
    <AppContext.Provider value={{ orders, drones, activityLog, notifications, mapStyle, placeOrder, updateOrderStatus, launchDroneForOrder, connectToDrone, disconnectFromDrone, commandRtl, removeNotification, updateDroneConnectionString, toggleMapStyle }}>
      {children}
    </AppContext.Provider>
  );
};