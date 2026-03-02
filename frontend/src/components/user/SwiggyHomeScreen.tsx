import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { RESTAURANTS, DELIVERY_LOCATIONS } from '../../constants';
import type { CartItem, MenuItem } from '../../types';
import HomeHeader from './home/HomeHeader';
import SearchBar from './home/SearchBar';
import BannerCarousel from './home/BannerCarousel';
import CategoryRow from './home/CategoryRow';
import RestaurantCard from './home/RestaurantCard';
import FloatingCart from './home/FloatingCart';
import BottomNav from './home/BottomNav';
import ProfileScreen from './ProfileScreen';
import OrdersScreen from './OrdersScreen';
import { X, MapPin } from 'lucide-react';

type Props = {
    cart: CartItem[];
    selectedRestaurantId: string;
    deliveryLocationId: string; // Add this
    onSelectLocation: (id: string) => void; // Add this
    onSelectRestaurant: (id: string) => void;
    onAddItem: (item: MenuItem) => void;
    onRemoveItem: (itemId: string) => void;
    onNext: () => void;
    onTrackOrder: () => void;
};

export default function SwiggyHomeScreen({
    cart,
    deliveryLocationId,
    onSelectLocation,
    onSelectRestaurant,
    onNext,
    onTrackOrder,
}: Props) {
    const [selectedCategory, setSelectedCategory] = useState('pizza');
    const [searchQuery, setSearchQuery] = useState('');
    const [activeTab, setActiveTab] = useState<'home' | 'search' | 'orders' | 'profile'>('home');
    const [isLocationModalOpen, setIsLocationModalOpen] = useState(false);

    // Get current location name
    const currentLocation = DELIVERY_LOCATIONS.find(l => l.id === deliveryLocationId)?.name || 'Select Location';

    const cartItemCount = cart.reduce((sum, item) => sum + item.quantity, 0);
    const cartTotal = cart.reduce((sum, item) => sum + item.price * item.quantity, 0);

    // Filter restaurants based on search
    const filteredRestaurants = RESTAURANTS.filter(r => {
        const matchesSearch = r.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            r.cuisine.toLowerCase().includes(searchQuery.toLowerCase());
        return matchesSearch;
    });

    const [showBackToTop, setShowBackToTop] = useState(false);
    const scrollContainerRef = React.useRef<HTMLDivElement>(null);

    const handleScroll = () => {
        if (scrollContainerRef.current) {
            setShowBackToTop(scrollContainerRef.current.scrollTop > 300);
        }
    };

    const scrollToTop = () => {
        scrollContainerRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
    };

    return (
        <div className="min-h-screen bg-warm-bg pb-28 font-sans">
            <AnimatePresence mode="wait">
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="max-w-md mx-auto relative min-h-screen bg-warm-bg shadow-2xl overflow-hidden"
                >
                    {(activeTab === 'home' || activeTab === 'search') && (
                        <>
                            <HomeHeader
                                location={currentLocation}
                                onClickLocation={() => setIsLocationModalOpen(true)}
                            />
                            <SearchBar searchQuery={searchQuery} setSearchQuery={setSearchQuery} />

                            <div
                                ref={scrollContainerRef}
                                onScroll={handleScroll}
                                className="overflow-y-auto h-[calc(100vh-130px)] pb-32 no-scrollbar hover:pr-1"
                            >
                                <BannerCarousel />
                                <CategoryRow
                                    selectedCategory={selectedCategory}
                                    setSelectedCategory={setSelectedCategory}
                                />
                                <div className="px-4 mt-2">
                                    <div className="flex items-center justify-between mb-4">
                                        <div>
                                            <h2 className="text-lg font-bold text-dark-text">Popular Near You</h2>
                                            <p className="text-xs text-gray-500">Fastest drone delivery available</p>
                                        </div>
                                    </div>
                                    <div className="space-y-1">
                                        {filteredRestaurants.map((restaurant) => (
                                            <RestaurantCard
                                                key={restaurant.id}
                                                restaurant={restaurant}
                                                onClick={() => onSelectRestaurant(restaurant.id)}
                                            />
                                        ))}
                                    </div>
                                </div>
                                <div className="h-10"></div>
                            </div>

                            {/* Back to Top Button only on Home */}
                            <AnimatePresence>
                                {showBackToTop && (
                                    <motion.button
                                        initial={{ opacity: 0, scale: 0.8 }}
                                        animate={{ opacity: 1, scale: 1 }}
                                        exit={{ opacity: 0, scale: 0.8 }}
                                        onClick={scrollToTop}
                                        className="absolute bottom-24 right-4 z-40 p-3 bg-white text-brand-orange rounded-full shadow-lg border border-orange-100"
                                    >
                                        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                            <path d="m18 15-6-6-6 6" />
                                        </svg>
                                    </motion.button>
                                )}
                            </AnimatePresence>

                            <FloatingCart
                                itemCount={cartItemCount}
                                totalPrice={cartTotal}
                                onClick={onNext}
                            />
                        </>
                    )}

                    {activeTab === 'orders' && <OrdersScreen onTrackOrder={onTrackOrder} />}

                    {activeTab === 'profile' && <ProfileScreen />}

                    <BottomNav activeTab={activeTab} setActiveTab={setActiveTab} />
                </motion.div>
            </AnimatePresence>

            {/* Location Selection Modal */}
            <AnimatePresence>
                {isLocationModalOpen && (
                    <div className="fixed inset-0 z-[60] flex items-end justify-center bg-black/60 backdrop-blur-sm p-4">
                        <motion.div
                            initial={{ y: '100%' }}
                            animate={{ y: 0 }}
                            exit={{ y: '100%' }}
                            className="w-full max-w-sm bg-white rounded-3xl p-6 shadow-2xl"
                        >
                            <div className="flex items-center justify-between mb-6">
                                <h3 className="text-lg font-bold text-dark-text">Select Location</h3>
                                <button
                                    onClick={() => setIsLocationModalOpen(false)}
                                    className="p-2 bg-gray-100 rounded-full hover:bg-gray-200"
                                >
                                    <X size={20} />
                                </button>
                            </div>

                            <div className="space-y-3">
                                {DELIVERY_LOCATIONS.map(loc => (
                                    <button
                                        key={loc.id}
                                        onClick={() => {
                                            onSelectLocation(loc.id);
                                            setIsLocationModalOpen(false);
                                        }}
                                        className={`w-full flex items-center gap-4 p-4 rounded-xl border transition-all ${deliveryLocationId === loc.id
                                            ? 'border-brand-orange bg-orange-50'
                                            : 'border-gray-100 hover:border-gray-200 hover:bg-gray-50'
                                            }`}
                                    >
                                        <div className={`w-10 h-10 rounded-full flex items-center justify-center ${deliveryLocationId === loc.id ? 'bg-brand-orange text-white' : 'bg-gray-100 text-gray-500'
                                            }`}>
                                            <MapPin size={20} />
                                        </div>
                                        <div className="text-left">
                                            <p className={`font-bold ${deliveryLocationId === loc.id ? 'text-brand-orange' : 'text-gray-800'}`}>
                                                {loc.name}
                                            </p>
                                            <p className="text-xs text-gray-500">Campus Drone Drop Point</p>
                                        </div>
                                        {deliveryLocationId === loc.id && (
                                            <div className="ml-auto w-3 h-3 rounded-full bg-brand-orange"></div>
                                        )}
                                    </button>
                                ))}
                            </div>
                        </motion.div>
                    </div>
                )}
            </AnimatePresence>
        </div>
    );
}
