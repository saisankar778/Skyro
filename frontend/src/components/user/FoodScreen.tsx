import React, { useMemo, useState } from 'react';
import { MENU_ITEMS, RESTAURANTS } from '@/constants';
import type { CartItem, MenuItem } from '@/types';

type Props = {
  cart: CartItem[];
  selectedRestaurantId: string;
  onSelectRestaurant: (id: string) => void;
  onAddItem: (item: MenuItem) => void;
  onRemoveItem: (itemId: string) => void;
  onNext: () => void;
};

export default function FoodScreen({
  cart,
  selectedRestaurantId,
  onSelectRestaurant,
  onAddItem,
  onRemoveItem,
  onNext,
}: Props) {
  const [query, setQuery] = useState('');

  const items = useMemo(() => {
    const base = MENU_ITEMS.filter((i) => i.restaurantId === selectedRestaurantId);
    const q = query.trim().toLowerCase();
    if (!q) return base;
    return base.filter((i) => i.name.toLowerCase().includes(q));
  }, [query, selectedRestaurantId]);

  const cartCount = useMemo(() => cart.reduce((sum, i) => sum + i.quantity, 0), [cart]);
  const cartTotal = useMemo(() => cart.reduce((sum, i) => sum + i.price * i.quantity, 0), [cart]);

  return (
    <div className="min-h-[calc(100vh-4rem)] bg-gray-900">
      <div className="max-w-5xl mx-auto px-4 py-6">
        <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
          <div>
            <h2 className="text-2xl font-extrabold text-white">Order food</h2>
            <p className="text-gray-300 mt-1">Choose a restaurant and add items to your cart</p>
          </div>

          <div className="w-full md:w-[380px]">
            <label className="text-sm font-semibold text-gray-200">Restaurant</label>
            <select
              value={selectedRestaurantId}
              onChange={(e) => onSelectRestaurant(e.target.value)}
              className="mt-2 w-full rounded-xl bg-gray-800 border border-white/10 px-4 py-3 text-white outline-none focus:ring-2 focus:ring-orange-500"
            >
              {RESTAURANTS.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="mt-5">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search in menu..."
            className="w-full rounded-xl bg-gray-800 border border-white/10 px-4 py-3 text-white outline-none focus:ring-2 focus:ring-orange-500"
          />
        </div>

        <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((item) => {
            const inCart = cart.find((c) => c.id === item.id)?.quantity ?? 0;
            return (
              <div key={item.id} className="rounded-2xl bg-gray-800 border border-white/10 shadow-xl p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-white font-bold">{item.name}</p>
                    <p className="text-gray-400 text-sm mt-1">₹{item.price.toFixed(2)}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    {inCart > 0 && (
                      <button
                        onClick={() => onRemoveItem(item.id)}
                        className="h-9 w-9 rounded-full bg-gray-700 hover:bg-gray-600 text-white font-bold"
                      >
                        -
                      </button>
                    )}
                    <button
                      onClick={() => onAddItem(item)}
                      className="h-9 px-4 rounded-full bg-orange-500 hover:bg-orange-600 text-white font-bold"
                    >
                      Add
                    </button>
                  </div>
                </div>

                {inCart > 0 && (
                  <p className="mt-3 text-sm text-orange-200">In cart: {inCart}</p>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {cartCount > 0 && (
        <div className="fixed bottom-0 left-0 right-0 border-t border-white/10 bg-gray-900/95 backdrop-blur">
          <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
            <div>
              <p className="text-white font-bold">{cartCount} items</p>
              <p className="text-gray-300 text-sm">Total: ₹{cartTotal.toFixed(2)}</p>
            </div>
            <button
              onClick={onNext}
              className="rounded-xl bg-green-500 hover:bg-green-600 text-white font-extrabold px-6 py-3"
            >
              Continue
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
