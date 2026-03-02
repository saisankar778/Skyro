import React, { useEffect, useRef, useState } from 'react';
import mapboxgl from 'mapbox-gl';
import 'mapbox-gl/dist/mapbox-gl.css';

// Set the access token
mapboxgl.accessToken = import.meta.env.VITE_MAPBOX_TOKEN || '';

interface DeliveryMapProps {
    droneLocation?: [number, number]; // [lng, lat]
    deliveryLocation?: [number, number]; // [lng, lat]
    restaurantLocation?: [number, number]; // [lng, lat]
    status?: string;
}

export default function DeliveryMap({
    droneLocation,
    deliveryLocation,
    restaurantLocation,
    status,
}: DeliveryMapProps) {
    const mapContainer = useRef<HTMLDivElement>(null);
    const mapRef = useRef<mapboxgl.Map | null>(null);
    const droneMarkerRef = useRef<mapboxgl.Marker | null>(null);
    const [mapLoaded, setMapLoaded] = useState(false);

    // Initialize Map
    useEffect(() => {
        if (mapRef.current || !mapContainer.current) return;

        mapRef.current = new mapboxgl.Map({
            container: mapContainer.current,
            style: 'mapbox://styles/mapbox/light-v11', // Default light style
            center: deliveryLocation || [78.4867, 17.3850], // Default to Hyderabad or delivery location
            zoom: 14,
            pitch: 0,
            bearing: 0,
            attributionControl: false,
            dragRotate: false, // Disable rotation for cleaner mobile experience
            touchZoomRotate: false, // Disable rotation on touch
        });

        // Add navigation control (zoom buttons)
        mapRef.current.addControl(
            new mapboxgl.NavigationControl({ showCompass: false }),
            'bottom-right'
        );

        mapRef.current.on('load', () => {
            setMapLoaded(true);
        });

        return () => {
            mapRef.current?.remove();
        };
    }, []);

    // Update Drone Marker
    useEffect(() => {
        if (!mapRef.current || !mapLoaded || !droneLocation) return;

        if (!droneMarkerRef.current) {
            // Create a custom DOM element for the marker if needed, 
            // or use the default marker with a custom color
            const el = document.createElement('div');
            el.className = 'drone-marker';
            el.style.backgroundImage = 'url(https://cdn-icons-png.flaticon.com/512/3063/3063823.png)'; // Example drone icon
            el.style.width = '40px';
            el.style.height = '40px';
            el.style.backgroundSize = 'contain';

            droneMarkerRef.current = new mapboxgl.Marker({ element: el })
                .setLngLat(droneLocation)
                .addTo(mapRef.current);
        } else {
            droneMarkerRef.current.setLngLat(droneLocation);
        }

        // Smoothly pan to drone if it moves
        mapRef.current.easeTo({
            center: droneLocation,
            zoom: 15,
            duration: 1000
        });

    }, [mapLoaded, droneLocation]);

    // Add/Update Route Line
    useEffect(() => {
        if (!mapRef.current || !mapLoaded || !droneLocation || !deliveryLocation) return;

        const routeSourceId = 'route';
        const routeLayerId = 'route-line';

        const routeData: GeoJSON.Feature<GeoJSON.LineString> = {
            type: 'Feature',
            properties: {},
            geometry: {
                type: 'LineString',
                coordinates: [
                    droneLocation,
                    deliveryLocation
                ]
            }
        };

        if (mapRef.current.getSource(routeSourceId)) {
            (mapRef.current.getSource(routeSourceId) as mapboxgl.GeoJSONSource).setData(routeData);
        } else {
            mapRef.current.addSource(routeSourceId, {
                type: 'geojson',
                data: routeData
            });

            mapRef.current.addLayer({
                id: routeLayerId,
                type: 'line',
                source: routeSourceId,
                layout: {
                    'line-join': 'round',
                    'line-cap': 'round'
                },
                paint: {
                    'line-color': '#ff5722',
                    'line-width': 5,
                    'line-opacity': 0.8
                }
            });
        }

        // Add Delivery Marker
        // We strictly only want one delivery marker.
        // Ideally we manage markers better, but for now let's just add it once or check existence.
        // For simplicity, we can just add a default marker.
        new mapboxgl.Marker({ color: '#4CAF50' }) // Green for delivery
            .setLngLat(deliveryLocation)
            .addTo(mapRef.current);

        if (restaurantLocation) {
            new mapboxgl.Marker({ color: '#EF4444' }) // Red for restaurant
                .setLngLat(restaurantLocation)
                .addTo(mapRef.current);
        }

    }, [mapLoaded, deliveryLocation, restaurantLocation]); // Run once on load for static locations, but drone moves

    return (
        <div
            ref={mapContainer}
            className="w-full h-full rounded-2xl overflow-hidden shadow-inner"
            style={{ minHeight: '100%' }}
        />
    );
}
