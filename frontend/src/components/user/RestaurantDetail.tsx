import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowLeft, Star, Clock, Info, Plus, Search } from 'lucide-react';
import { RESTAURANTS, MENU_ITEMS } from '../../constants';
import type { CartItem, Restaurant, MenuItem } from '../../types';
import FloatingCart from './home/FloatingCart';

type Props = {
    restaurantId: string;
    cart: CartItem[];
    onBack: () => void;
    onAddItem: (item: MenuItem) => void;
    onRemoveItem: (itemId: string) => void;
    onNext: () => void;
};

export default function RestaurantDetail({
    restaurantId,
    cart,
    onBack,
    onAddItem,
    onRemoveItem,
    onNext,
}: Props) {
    const restaurant = RESTAURANTS.find((r) => r.id === restaurantId);
    const restaurantMenu = MENU_ITEMS.filter((item) => item.restaurantId === restaurantId);

    const [activeCategory, setActiveCategory] = useState('Recommended');
    const [scrollY, setScrollY] = useState(0);

    // Group menu items by category (simulated for now)
    const categories = ['Recommended', 'Bestsellers', 'New Arrivals', 'Main Course', 'Beverages'];

    useEffect(() => {
        const handleScroll = () => setScrollY(window.scrollY);
        window.addEventListener('scroll', handleScroll);
        return () => window.removeEventListener('scroll', handleScroll);
    }, []);

    if (!restaurant) return <div>Restaurant not found</div>;

    const cartItemCount = cart.reduce((sum, item) => sum + item.quantity, 0);
    const cartTotal = cart.reduce((sum, item) => sum + item.price * item.quantity, 0);

    const getQuantity = (itemId: string) => {
        return cart.find(item => item.id === itemId)?.quantity || 0;
    };

    return (
        <div className="min-h-screen bg-warm-bg pb-24">
            {/* Animated Header */}
            <motion.div
                className="fixed top-0 left-0 right-0 z-50 bg-white/0 transition-colors duration-300"
                style={{ backgroundColor: scrollY > 50 ? 'rgba(255, 255, 255, 0.95)' : 'transparent' }}
            >
                <div className="px-4 py-3 flex items-center gap-4">
                    <button
                        onClick={onBack}
                        className={`p-2 rounded-full backdrop-blur-md transition-colors ${scrollY > 50 ? 'bg-gray-100 text-gray-800' : 'bg-black/30 text-white'}`}
                    >
                        <ArrowLeft size={20} />
                    </button>
                    <motion.span
                        initial={{ opacity: 0 }}
                        animate={{ opacity: scrollY > 100 ? 1 : 0 }}
                        className="font-bold text-gray-800 text-lg truncate flex-1"
                    >
                        {restaurant.name}
                    </motion.span>
                </div>
            </motion.div>

            {/* Hero Section */}
            <div className="relative h-64 bg-gray-200 overflow-hidden">
                <motion.div
                    className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent z-10"
                />
                {/* Mock Image Background */}
                <div className="absolute inset-0 bg-gray-800 flex items-center justify-center">
                    <span className="text-6xl">
                        {restaurant.cuisine.toLowerCase().includes('pizza') ? '🍕' :
                            restaurant.cuisine.toLowerCase().includes('burger') ? '🍔' :
                                restaurant.cuisine.toLowerCase().includes('waffle') ? '🧇' : '🍽️'}
                    </span>
                </div>

                <div className="absolute bottom-0 left-0 right-0 p-4 z-20 text-white">
                    <h1 className="text-3xl font-bold mb-2 shadow-sm">{restaurant.name}</h1>
                    <p className="text-white/80 text-sm mb-3">{restaurant.cuisine}</p>

                    <div className="flex items-center gap-4 text-sm font-medium">
                        <div className="flex items-center gap-1 bg-green-600 px-2 py-0.5 rounded-lg">
                            <span className="font-bold">{restaurant.rating}</span>
                            <Star size={12} className="fill-white" />
                        </div>
                        <span>•</span>
                        <div className="flex items-center gap-1">
                            <Clock size={14} />
                            <span>{restaurant.deliveryTime}</span>
                        </div>
                        <span>•</span>
                        <span>₹{restaurant.priceForTwo} for two</span>
                    </div>
                </div>
            </div>

            {/* Menu Categories (Sticky) */}
            <div className="sticky top-14 z-40 bg-warm-bg border-b border-gray-200 px-4 py-2 overflow-x-auto whitespace-nowrap scrollbar-hide">
                {categories.map(cat => (
                    <button
                        key={cat}
                        onClick={() => setActiveCategory(cat)}
                        className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors mr-2 ${activeCategory === cat
                            ? 'bg-brand-orange text-white shadow-md'
                            : 'bg-white text-gray-600 border border-gray-200'
                            }`}
                    >
                        {cat}
                    </button>
                ))}
            </div>

            {/* Menu List */}
            <div className="px-4 py-4 space-y-6">
                <div>
                    <div className="flex items-center justify-between mb-4">
                        <h3 className="text-xl font-bold text-dark-text">{activeCategory}</h3>
                        <button className="text-gray-400">
                            <Info size={16} />
                        </button>
                    </div>

                    <div className="space-y-6">
                        {restaurantMenu.map((item) => (
                            <div key={item.id} className="flex justify-between gap-4 pb-6 border-b border-gray-100 last:border-0">
                                <div className="flex-1">
                                    <div className="flex items-center gap-2 mb-1">
                                        <span className={`w-4 h-4 border-2 flex items-center justify-center rounded-sm ${item.name.includes('Chicken') || item.name.includes('Non-Veg') ? 'border-red-500' : 'border-green-600'}`}>
                                            <span className={`w-2 h-2 rounded-full ${item.name.includes('Chicken') || item.name.includes('Non-Veg') ? 'bg-red-500' : 'bg-green-600'}`}></span>
                                        </span>
                                        <span className="text-brand-orange text-xs font-bold">Bestseller</span>
                                    </div>
                                    <h4 className="text-base font-bold text-gray-900 mb-1">{item.name}</h4>
                                    <p className="text-gray-700 font-medium text-sm mb-2">₹{item.price}</p>
                                    <p className="text-gray-400 text-xs line-clamp-2">
                                        Mouth-watering {item.name} prepared with fresh ingredients and served hot.
                                    </p>
                                </div>

                                <div className="relative w-32 flex-shrink-0">
                                    <div className="w-32 h-28 bg-gray-100 rounded-xl overflow-hidden shadow-sm">
                                        {/* Mock Item Image */}
                                        <div className="w-full h-full bg-gray-200 flex items-center justify-center text-4xl">
                                            {item.name.includes('Pizza') ? '🍕' : item.name.includes('Burger') ? '🍔' : '🍲'}
                                        </div>
                                    </div>

                                    <div className="absolute -bottom-3 left-1/2 -translate-x-1/2 w-24">
                                        {getQuantity(item.id) === 0 ? (
                                            <button
                                                onClick={() => onAddItem(item)}
                                                className="w-full bg-white text-green-600 font-bold text-sm py-2 rounded-lg border border-gray-200 shadow-sm uppercase hover:bg-green-50 transition-colors"
                                            >
                                                ADD
                                            </button>
                                        ) : (
                                            <div className="w-full bg-white text-green-600 font-bold text-sm py-1.5 rounded-lg border border-gray-200 shadow-sm flex items-center justify-between px-2">
                                                <button onClick={() => onRemoveItem(item.id)} className="text-xl font-bold px-1 hover:text-green-800">-</button>
                                                <span>{getQuantity(item.id)}</span>
                                                <button onClick={() => onAddItem(item)} className="text-xl font-bold px-1 hover:text-green-800">+</button>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            <FloatingCart
                itemCount={cartItemCount}
                totalPrice={cartTotal}
                onClick={onNext}
            />
        </div>
    );
}
