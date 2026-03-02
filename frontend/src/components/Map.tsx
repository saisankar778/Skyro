import React, { useEffect, useMemo, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline } from 'react-leaflet';
import L from 'leaflet';
import { Drone, Restaurant, DeliveryLocation } from '../types';
import { DroneIcon, BuildingIcon, LocationMarkerIcon } from './Icons';
import 'leaflet/dist/leaflet.css';

type MapStyle = 'schematic' | 'satellite';

interface MapProps {
  dronesToDisplay: Drone[];
  restaurantsToDisplay: Restaurant[];
  locationsToDisplay: DeliveryLocation[];
  mapStyle?: MapStyle;
  showRestaurants?: boolean;
  showLocations?: boolean;
  showOnlyConnectedDrones?: boolean;
}

// Fix for default markers in react-leaflet
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

// Custom icons
const createCustomIcon = (iconComponent: React.ReactNode, color: string, size: number = 32) => {
  const iconHtml = `
    <div style="
      background-color: ${color};
      border: 2px solid white;
      border-radius: 50%;
      width: ${size}px;
      height: ${size}px;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 2px 4px rgba(0,0,0,0.3);
    ">
      <div style="color: white; font-size: 16px;">🚁</div>
    </div>
  `;
  
  return L.divIcon({
    html: iconHtml,
    className: 'custom-icon',
    iconSize: [size, size],
    iconAnchor: [size/2, size/2],
  });
};

// Drone image-based icon from public/D.png
const createDroneIcon = (color: string, size: number = 32) => {
  const iconHtml = `
    <div style="
      background-color: ${color};
      border: 2px solid white;
      border-radius: 50%;
      width: ${size}px;
      height: ${size}px;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 2px 4px rgba(0,0,0,0.3);
    ">
      <img src="/D.png" alt="Drone" style="width: ${size-8}px; height: ${size-8}px; object-fit: contain;" />
    </div>
  `;
  return L.divIcon({
    html: iconHtml,
    className: 'custom-drone-icon',
    iconSize: [size, size],
    iconAnchor: [size/2, size/2],
  });
};

const restaurantIcon = createCustomIcon(<BuildingIcon />, '#10b981', 28);
const deliveryIcon = createCustomIcon(<LocationMarkerIcon />, '#3b82f6', 28);
const droneIcon = createDroneIcon('#06b6d4', 32);
const droneMovingIcon = createDroneIcon('#f59e0b', 32);
const droneDisconnectedIcon = createDroneIcon('#6b7280', 32);

type LatLon = { lat: number; lon: number };

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

const SmoothMarker: React.FC<{
  position: LatLon;
  icon: L.DivIcon;
  animationMs?: number;
  children?: React.ReactNode;
}> = ({ position, icon, animationMs = 650, children }) => {
  const markerRef = useRef<L.Marker | null>(null);
  const lastPosRef = useRef<LatLon | null>(null);
  const rafRef = useRef<number | null>(null);

  const startPos = lastPosRef.current;
  const nextPos = position;

  useEffect(() => {
    const marker = markerRef.current;
    if (!marker) return;

    if (!startPos) {
      marker.setLatLng([nextPos.lat, nextPos.lon]);
      lastPosRef.current = nextPos;
      return;
    }

    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    const t0 = performance.now();
    const from = startPos;
    const to = nextPos;

    const tick = (now: number) => {
      const t = Math.min(1, (now - t0) / animationMs);
      const ease = 1 - Math.pow(1 - t, 3);
      const lat = lerp(from.lat, to.lat, ease);
      const lon = lerp(from.lon, to.lon, ease);
      marker.setLatLng([lat, lon]);
      if (t < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        lastPosRef.current = to;
        rafRef.current = null;
      }
    };

    rafRef.current = requestAnimationFrame(tick);

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    };
  }, [animationMs, nextPos.lat, nextPos.lon]);

  useEffect(() => () => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
  }, []);

  return (
    <Marker
      position={[position.lat, position.lon]}
      icon={icon}
      ref={(m) => {
        markerRef.current = (m as unknown as L.Marker) || null;
      }}
    >
      {children}
    </Marker>
  );
};

const Map: React.FC<MapProps> = ({ 
  dronesToDisplay, 
  restaurantsToDisplay, 
  locationsToDisplay, 
  mapStyle = 'schematic',
  showRestaurants = true,
  showLocations = true,
  showOnlyConnectedDrones = false,
}) => {
  const mapRef = useRef<L.Map>(null);

  const droneIconById = useMemo(() => {
    const byId: Record<string, L.DivIcon> = {};
    dronesToDisplay.forEach((drone) => {
      const isMoving = drone.status === 'On Mission' || drone.status === 'Returning Home';
      const isConnected = drone.isConnected;

      let icon = droneDisconnectedIcon;
      if (isConnected) icon = isMoving ? droneMovingIcon : droneIcon;
      byId[drone.id] = icon;
    });
    return byId;
  }, [dronesToDisplay]);

  // Calculate center point
  const allPoints = [
    ...dronesToDisplay.map(d => d.location), 
    ...dronesToDisplay.map(d => d.homeLocation),
    ...restaurantsToDisplay.map(r => r.location), 
    ...locationsToDisplay.map(l => l.location)
  ];
  
  const centerLat = allPoints.length > 0 ? allPoints.reduce((sum, p) => sum + p.lat, 0) / allPoints.length : 16.463;
  const centerLon = allPoints.length > 0 ? allPoints.reduce((sum, p) => sum + p.lon, 0) / allPoints.length : 80.508;

  // Update map style when prop changes
  useEffect(() => {
    if (mapRef.current) {
      const map = mapRef.current;
      map.eachLayer((layer) => {
        if (layer instanceof L.TileLayer) {
          map.removeLayer(layer);
        }
      });

      if (mapStyle === 'satellite') {
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
          attribution: '© Esri — Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
        }).addTo(map);
      } else {
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          attribution: '© OpenStreetMap contributors'
        }).addTo(map);
      }
    }
  }, [mapStyle]);

  // Auto-fit to show moving drone and its destination
  useEffect(() => {
    if (!mapRef.current) return;
    const map = mapRef.current;
    const moving = dronesToDisplay.filter(d => (d.status === 'On Mission' || d.status === 'Returning Home') && d.destination);
    if (moving.length > 0) {
      const points: L.LatLngExpression[] = [];
      moving.forEach(d => {
        points.push([d.location.lat, d.location.lon]);
        if (d.destination) points.push([d.destination.lat, d.destination.lon]);
      });
      const bounds = L.latLngBounds(points as [number, number][]);
      map.fitBounds(bounds, { padding: [40, 40] });
    }
  }, [dronesToDisplay]);

  return (
    <div className="w-full h-full border-2 border-gray-700 rounded-lg overflow-hidden shadow-lg">
      <MapContainer
        center={[centerLat, centerLon]}
        zoom={16}
        style={{ height: '100%', width: '100%' }}
        ref={mapRef}
      >
        {/* Base map layer */}
        {mapStyle === 'satellite' ? (
          <TileLayer
            url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
            attribution='© Esri — Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
          />
        ) : (
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='© OpenStreetMap contributors'
          />
        )}

        {/* Restaurants */}
        {showRestaurants && restaurantsToDisplay.map(restaurant => (
          <Marker
            key={restaurant.id}
            position={[restaurant.location.lat, restaurant.location.lon]}
            icon={restaurantIcon}
          >
            <Popup>
              <div className="text-center">
                <div className="font-bold text-green-600">🏢 {restaurant.name}</div>
                <div className="text-sm text-gray-600">Restaurant</div>
              </div>
            </Popup>
          </Marker>
        ))}

        {/* Delivery Locations */}
        {showLocations && locationsToDisplay.map(location => (
          <Marker
            key={location.id}
            position={[location.location.lat, location.location.lon]}
            icon={deliveryIcon}
          >
            <Popup>
              <div className="text-center">
                <div className="font-bold text-blue-600">📍 {location.name}</div>
                <div className="text-sm text-gray-600">Delivery Point</div>
              </div>
            </Popup>
          </Marker>
        ))}

        {/* Drones */}
        {dronesToDisplay
          .filter(drone => (!showOnlyConnectedDrones || drone.isConnected))
          .filter(drone => drone.location && drone.location.lat !== 0 && drone.location.lon !== 0)
          .map(drone => {
          const isMoving = drone.status === 'On Mission' || drone.status === 'Returning Home';
          const icon = droneIconById[drone.id] || droneIcon;

          return (
            <React.Fragment key={drone.id}>
              {/* Flight path for moving drones */}
              {isMoving && drone.destination && (
                <Polyline
                  positions={[
                    [drone.location.lat, drone.location.lon],
                    [drone.destination.lat, drone.destination.lon]
                  ]}
                  color="#f59e0b"
                  weight={3}
                  dashArray="10, 10"
                  opacity={0.7}
                />
              )}
              
              <SmoothMarker
                position={drone.location}
                icon={icon}
                animationMs={650}
              >
                <Popup>
                  <div className="text-center">
                    <div className="font-bold text-cyan-600">🚁 {drone.id}</div>
                    <div className="text-sm">
                      <div>Status: <span className={`font-semibold ${
                        isMoving ? 'text-yellow-600' : 
                        drone.isConnected ? 'text-green-600' : 'text-gray-600'
                      }`}>{drone.status}</span></div>
                      <div>Battery: {drone.battery}%</div>
                      <div>Connected: <span className={drone.isConnected ? 'text-green-600' : 'text-red-600'}>
                        {drone.isConnected ? 'Yes' : 'No'}
                      </span></div>
                      {isMoving && drone.destination && (
                        <div className="text-xs text-gray-500 mt-1">
                          Flying to: {drone.destination.lat.toFixed(6)}, {drone.destination.lon.toFixed(6)}
                        </div>
                      )}
                    </div>
                  </div>
                </Popup>
              </SmoothMarker>
            </React.Fragment>
          );
        })}
      </MapContainer>
    </div>
  );
};

export default Map;
