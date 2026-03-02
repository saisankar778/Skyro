import React, { useState, useEffect } from 'react';
import { RESTAURANTS } from '../../constants';
import type { CartItem, MenuItem } from '../../types';
import './HomeScreen.css';

type Props = {
  cart: CartItem[];
  selectedRestaurantId: string;
  onSelectRestaurant: (id: string) => void;
  onAddItem: (item: MenuItem) => void;
  onRemoveItem: (itemId: string) => void;
  onNext: () => void;
};

const categories = [
  { id: 'pizza', name: 'Pizza', icon: '🍕' },
  { id: 'biryani', name: 'Biryani', icon: '🍛' },
  { id: 'burger', name: 'Burger', icon: '🍔' },
  { id: 'healthy', name: 'Healthy', icon: '🥗' },
  { id: 'offers', name: 'Offers', icon: '🎁' },
  { id: 'desserts', name: 'Desserts', icon: '🍰' },
];

export default function HomeScreen({
  cart,
  selectedRestaurantId,
  onSelectRestaurant,
  onAddItem,
  onRemoveItem,
  onNext,
}: Props) {
  const [selectedCategory, setSelectedCategory] = useState('pizza');
  const [searchQuery, setSearchQuery] = useState('');
  const [location, setLocation] = useState('Block A, Main Campus');

  const cartItemCount = cart.reduce((sum, item) => sum + item.quantity, 0);

  // Animation on mount
  useEffect(() => {
    const timer = setTimeout(() => {
      // Add entrance animations after component mounts
    }, 100);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-b from-orange-50 to-white pb-20">
      {/* Sticky Header */}
      <div className="sticky top-0 z-40 bg-white/95 backdrop-blur-md border-b border-gray-100">
        <div className="px-4 py-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-gray-500">Delivering to</p>
              <div className="flex items-center gap-1">
                <h2 className="text-base font-semibold text-gray-900">{location}</h2>
                <svg className="w-4 h-4 text-orange-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </div>
            </div>
            <div className="w-8 h-8 rounded-full bg-gradient-to-r from-orange-400 to-orange-500 flex items-center justify-center">
              <span className="text-white text-sm font-semibold">S</span>
            </div>
          </div>
          <p className="text-xs text-orange-600 mt-1 font-medium">🚁 Fastest Drone Delivery in Campus</p>
        </div>
      </div>

      {/* Search Bar */}
      <div className="px-4 py-4">
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <svg className="h-5 w-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="block w-full pl-10 pr-3 py-3 border border-gray-200 rounded-2xl bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent transition-all duration-200"
            placeholder="Search for restaurants or dishes..."
          />
        </div>
      </div>

      {/* Promotional Banner */}
      <div className="px-4 mb-6">
        <div className="relative rounded-3xl bg-gradient-to-r from-orange-500 to-red-500 p-6 overflow-hidden animate-float">
          <div className="relative z-10">
            <h3 className="text-white text-xl font-bold mb-2 animate-fadeInUp">Free Drone Delivery Today 🚁</h3>
            <p className="text-white/90 text-sm mb-4 animate-fadeInUp stagger-1">Under 10 minutes anywhere in campus</p>
            <button className="bg-white text-orange-600 px-4 py-2 rounded-full text-sm font-semibold hover:bg-gray-50 transition-colors animate-fadeInUp stagger-2">
              Order Now
            </button>
          </div>
          <div className="absolute top-0 right-0 w-32 h-32 bg-white/10 rounded-full -mr-16 -mt-16"></div>
          <div className="absolute bottom-0 right-0 w-24 h-24 bg-white/10 rounded-full -mr-12 -mb-12"></div>
        </div>
      </div>

      {/* Categories */}
      <div className="px-4 mb-6">
        <div className="flex gap-4 overflow-x-auto scrollbar-hide">
          {categories.map((category, index) => (
            <button
              key={category.id}
              onClick={() => setSelectedCategory(category.id)}
              className={`flex flex-col items-center min-w-fit transition-all duration-200 animate-slideInRight stagger-${index + 1} ${
                selectedCategory === category.id ? 'scale-110 category-selected' : 'scale-100 hover-scale'
              }`}
            >
              <div
                className={`w-16 h-16 rounded-full flex items-center justify-center text-2xl transition-all duration-200 ${
                  selectedCategory === category.id
                    ? 'bg-orange-500 shadow-lg'
                    : 'bg-gray-100 hover:bg-gray-200'
                }`}
              >
                {category.icon}
              </div>
              <span className="text-xs mt-2 text-gray-700 font-medium">{category.name}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Popular Section */}
      <div className="px-4 mb-4">
        <div className="flex items-center justify-between mb-4">
          <div className="animate-fadeInUp">
            <h2 className="text-xl font-bold text-gray-900">Popular Near You</h2>
            <p className="text-sm text-gray-500">Fastest drone delivery available</p>
          </div>
        </div>

        {/* Restaurant Cards */}
        <div className="space-y-4">
          {RESTAURANTS.map((restaurant, index) => (
            <div
              key={restaurant.id}
              onClick={() => onSelectRestaurant(restaurant.id)}
              className={`bg-white rounded-2xl shadow-sm hover:shadow-md transition-all duration-200 overflow-hidden cursor-pointer transform hover:scale-[0.98] hover-lift restaurant-card stagger-${index + 1}`}
              style={{
                animationDelay: `${index * 100}ms`,
              }}
            >
              <div className="relative">
                <div className="h-48 bg-gradient-to-br from-orange-100 to-red-100 flex items-center justify-center">
                  <span className="text-6xl">🍽️</span>
                </div>
                <div className="absolute top-2 left-2 bg-yellow-400 text-black px-2 py-1 rounded-full text-xs font-bold">
                  ⭐ {restaurant.rating || '4.5'}
                </div>
                <div className="absolute top-2 right-2 bg-white/90 backdrop-blur px-2 py-1 rounded-full text-xs font-semibold">
                  🚁 {restaurant.deliveryTime || '10-15'} min
                </div>
                <div className="absolute bottom-2 right-2 bg-blue-500 text-white px-2 py-1 rounded-full text-xs font-bold">
                  Drone
                </div>
              </div>
              <div className="p-4">
                <h3 className="font-bold text-gray-900 text-lg">{restaurant.name}</h3>
                <p className="text-sm text-gray-500 mb-2">{restaurant.cuisine || 'Multi-cuisine'}</p>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4 text-sm text-gray-600">
                    <span>⏱️ {restaurant.deliveryTime || '10-15'} min</span>
                    <span>💰 ₹{restaurant.priceForTwo || '300'} for two</span>
                  </div>
                  {restaurant.offer && (
                    <div className="bg-orange-100 text-orange-700 px-2 py-1 rounded-full text-xs font-bold">
                      {restaurant.offer}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Floating Cart Button */}
      {cartItemCount > 0 && (
        <div className="fixed bottom-24 right-4 z-50">
          <button
            onClick={onNext}
            className={`relative bg-gradient-to-r from-orange-500 to-orange-600 text-white rounded-full p-4 shadow-lg hover:shadow-xl transition-all duration-200 transform hover:scale-110 ${
              cartItemCount > 0 ? 'cart-bounce' : ''
            }`}
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
            <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center font-bold animate-pulse">
              {cartItemCount}
            </span>
          </button>
        </div>
      )}

      {/* Bottom Navigation */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 z-40">
        <div className="flex items-center justify-around py-2">
          {[
            { id: 'home', icon: '🏠', label: 'Home', active: true },
            { id: 'search', icon: '🔍', label: 'Search', active: false },
            { id: 'orders', icon: '📦', label: 'Orders', active: false },
            { id: 'profile', icon: '👤', label: 'Profile', active: false },
          ].map((tab) => (
            <button
              key={tab.id}
              className={`flex flex-col items-center py-2 px-3 transition-all duration-200 ${
                tab.active ? 'text-orange-500' : 'text-gray-400 hover:text-gray-600'
              }`}
            >
              <span className="text-xl mb-1">{tab.icon}</span>
              <span className="text-xs">{tab.label}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
