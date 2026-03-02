import React from 'react';
import { motion } from 'framer-motion';
import { Restaurant } from '../../../types';
import { Star, Clock, Zap } from 'lucide-react';

type Props = {
    restaurant: Restaurant;
    onClick: () => void;
};

export default function RestaurantCard({ restaurant, onClick }: Props) {
    return (
        <motion.div
            layout
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            whileTap={{ scale: 0.98 }}
            onClick={onClick}
            className="bg-white rounded-[20px] shadow-sm border border-gray-100 overflow-hidden cursor-pointer group hover:shadow-xl transition-shadow duration-300 mb-5 last:mb-24"
        >
            <div className="relative h-48 overflow-hidden">
                {/* Image Placeholder with Gradient */}
                <div className="absolute inset-0 bg-gradient-to-br from-gray-200 to-gray-100 flex items-center justify-center group-hover:scale-105 transition-transform duration-500">
                    {/* In a real app, use <img src={restaurant.image} /> */}
                    <span className="text-6xl filter drop-shadow-md">
                        {restaurant.cuisine.toLowerCase().includes('pizza') ? '🍕' :
                            restaurant.cuisine.toLowerCase().includes('burger') ? '🍔' :
                                restaurant.cuisine.toLowerCase().includes('biryani') ? '🍛' :
                                    restaurant.cuisine.toLowerCase().includes('waffle') ? '🧇' :
                                        restaurant.cuisine.toLowerCase().includes('ice cream') ? '🍦' :
                                            restaurant.cuisine.toLowerCase().includes('snacks') ? '🥘' : '🍽️'}
                    </span>
                </div>

                {/* Overlay Badges */}
                <div className="absolute top-3 left-3 flex gap-2">
                    <div className="bg-white/90 backdrop-blur-md px-2.5 py-1 rounded-lg text-[10px] font-bold text-dark-text shadow-sm flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></span>
                        Open
                    </div>
                </div>

                <div className="absolute bottom-0 left-0 right-0 h-2/3 bg-gradient-to-t from-black/80 via-black/40 to-transparent p-4 flex flex-col justify-end">
                    <div className="flex items-center justify-between items-end">
                        <div>
                            <h3 className="text-white text-xl font-bold leading-tight drop-shadow-sm mb-1">{restaurant.name}</h3>
                            <p className="text-white/80 text-xs font-medium truncate max-w-[200px]">{restaurant.cuisine}</p>
                        </div>
                        <div className="bg-white/10 backdrop-blur-md border border-white/20 rounded-lg px-2 py-1 flex flex-col items-center min-w-[50px]">
                            <span className="text-white text-[10px] uppercase font-bold tracking-wider">Rating</span>
                            <div className="flex items-center gap-1 text-white font-bold text-sm">
                                {restaurant.rating} <Star size={10} className="fill-offer-yellow text-offer-yellow" />
                            </div>
                        </div>
                    </div>
                </div>

                {/* Offer Tag */}
                {restaurant.offer && (
                    <div className="absolute top-3 right-0 bg-brand-orange text-white text-[10px] font-bold px-3 py-1 rounded-l-full shadow-md uppercase tracking-wide transform group-hover:translate-x-1 transition-transform">
                        {restaurant.offer}
                    </div>
                )}
            </div>

            <div className="p-4 bg-white">
                <div className="flex items-center justify-between mb-3 text-sm font-medium text-gray-500">
                    <div className="flex items-center gap-1.5 bg-gray-50 px-2.5 py-1 rounded-full">
                        <Clock size={14} className="text-brand-orange" />
                        <span className="text-dark-text">{restaurant.deliveryTime}</span>
                    </div>
                    <div className="flex items-center gap-1.5 bg-gray-50 px-2.5 py-1 rounded-full">
                        <span className="text-gray-400">₹</span>
                        <span className="text-dark-text">{restaurant.priceForTwo} for two</span>
                    </div>
                </div>

                <div className="pt-3 border-t border-gray-100 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <div className="p-1.5 bg-blue-50 rounded-full">
                            <Zap size={12} className="text-blue-600 fill-blue-600" />
                        </div>
                        <span className="text-[11px] font-semibold text-blue-600">Drone Delivery Available</span>
                    </div>
                    <motion.button
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        className="text-brand-orange text-xs font-bold uppercase tracking-wide hover:underline"
                    >
                        View Menu
                    </motion.button>
                </div>
            </div>
        </motion.div>
    );
}
