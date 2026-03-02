import React, { useContext, useEffect, useMemo, useState } from 'react';
import { AppContext } from '../context/AppContext';
import { DELIVERY_LOCATIONS, RESTAURANTS } from '../constants';
import type { CartItem, MenuItem } from '../types';
import SwiggyHomeScreen from './user/SwiggyHomeScreen';
import RestaurantDetail from './user/RestaurantDetail';
import CartDrawer from './user/CartDrawer';
import BlockScreen from './user/BlockScreen';
import PaymentScreen from './user/PaymentScreen';
import TrackingScreen from './user/TrackingScreen';
import type { UserFlowStep } from './user/types';

const STORAGE_KEYS = {
  // No auth keys for demo mode
};

const UserView: React.FC = () => {
  const context = useContext(AppContext);
  const apiBase = (import.meta.env.VITE_API_BASE as string | undefined) || '';

  const [step, setStep] = useState<UserFlowStep>('food');

  const [selectedRestaurantId, setSelectedRestaurantId] = useState<string>(RESTAURANTS[0].id);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [deliveryLocationId, setDeliveryLocationId] = useState<string>(DELIVERY_LOCATIONS[0].id);

  const cartTotal = useMemo(() => cart.reduce((sum, item) => sum + item.price * item.quantity, 0), [cart]);

  const handleAddItem = (item: MenuItem) => {
    setCart((prev) => {
      const existing = prev.find((c) => c.id === item.id);
      if (existing) {
        return prev.map((c) => (c.id === item.id ? { ...c, quantity: c.quantity + 1 } : c));
      }
      return [...prev, { ...item, quantity: 1 }];
    });
  };

  const handleRemoveItem = (itemId: string) => {
    setCart((prev) => {
      const existing = prev.find((c) => c.id === itemId);
      if (!existing) return prev;
      if (existing.quantity <= 1) return prev.filter((c) => c.id !== itemId);
      return prev.map((c) => (c.id === itemId ? { ...c, quantity: c.quantity - 1 } : c));
    });
  };

  const handlePaymentVerified = () => {
    if (!context) return;
    context.placeOrder('demo_user', cart, cartTotal, deliveryLocationId, selectedRestaurantId);
    setCart([]);
    setStep('tracking');
  };

  if (!apiBase) {
    return (
      <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-6 text-gray-200">
        <div className="max-w-lg w-full rounded-2xl bg-gray-800 border border-white/10 p-6 shadow-2xl">
          <p className="text-white font-extrabold text-xl">Skyro is not configured</p>
          <p className="text-gray-300 mt-2">
            Set <code className="px-1 rounded bg-black/30">VITE_API_BASE</code> to your backend-orders URL.
          </p>
        </div>
      </div>
    );
  }

  if (step === 'food') {
    return (
      <SwiggyHomeScreen
        cart={cart}
        deliveryLocationId={deliveryLocationId}
        onSelectLocation={setDeliveryLocationId}
        selectedRestaurantId={selectedRestaurantId}
        onSelectRestaurant={(id) => {
          setSelectedRestaurantId(id);

          if (selectedRestaurantId !== id && cart.length > 0) {
            if (confirm("Start fresh from this restaurant? Your current cart will be cleared.")) {
              setCart([]);
              setStep('restaurant');
            }
          } else {
            setStep('restaurant');
          }
        }}
        onAddItem={handleAddItem}
        onRemoveItem={handleRemoveItem}
        onNext={() => setStep('cart')}
        onTrackOrder={() => setStep('tracking')}
      />
    );
  }

  if (step === 'restaurant') {
    return (
      <RestaurantDetail
        restaurantId={selectedRestaurantId}
        cart={cart}
        onBack={() => setStep('food')}
        onAddItem={handleAddItem}
        onRemoveItem={handleRemoveItem}
        onNext={() => setStep('cart')}
      />
    );
  }

  if (step === 'cart') {
    return (
      <CartDrawer
        cart={cart}
        onBack={() => setStep('restaurant')}
        onAddItem={handleAddItem}
        onRemoveItem={handleRemoveItem}
        onCheckout={() => setStep('block')}
      />
    );
  }

  if (step === 'block') {
    return (
      <BlockScreen
        selectedLocationId={deliveryLocationId}
        onSelect={setDeliveryLocationId}
        onBack={() => setStep('food')}
        onNext={() => setStep('payment')}
      />
    );
  }
  if (step === 'payment') {
    return (
      <PaymentScreen
        apiBase={apiBase}
        accessToken='demo'
        phone='demo_user'
        cart={cart}
        total={cartTotal}
        onBack={() => setStep('block')}
        onPaymentVerified={handlePaymentVerified}
      />
    );
  }

  // Handle explicit tracking step or check context for active orders
  // For now, if step is tracking, show TrackingScreen
  if (step === 'tracking') {
    return (
      <TrackingScreen userId='demo_user' onBrowse={() => setStep('food')} />
    );
  }

  return <TrackingScreen userId='demo_user' onBrowse={() => setStep('food')} />;
};

export default UserView;