import React from 'react';
import { motion } from 'framer-motion';
import { Home, Search, ShoppingBag, User } from 'lucide-react';

type TabId = 'home' | 'search' | 'orders' | 'profile';

type Props = {
    activeTab: TabId;
    setActiveTab: (tab: TabId) => void;
};

export default function BottomNav({ activeTab, setActiveTab }: Props) {
    const tabs = [
        { id: 'home', icon: Home, label: 'Home' },
        { id: 'search', icon: Search, label: 'Search' },
        { id: 'orders', icon: ShoppingBag, label: 'Orders' },
        { id: 'profile', icon: User, label: 'Profile' },
    ] as const;

    return (
        <div className="fixed bottom-0 left-0 right-0 bg-white/95 backdrop-blur-lg border-t border-gray-100 pb-safe pt-2 z-40 shadow-lg">
            <div className="flex items-center justify-around max-w-md mx-auto px-2">
                {tabs.map((tab) => {
                    const isActive = activeTab === tab.id;
                    const Icon = tab.icon;

                    return (
                        <motion.button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id)}
                            className="relative flex flex-col items-center py-2 px-4 rounded-xl transition-colors"
                            whileTap={{ scale: 0.9 }}
                        >
                            <div className="relative z-10">
                                <Icon
                                    size={24}
                                    strokeWidth={isActive ? 2.5 : 2}
                                    className={`transition-colors duration-300 ${isActive ? 'text-brand-orange' : 'text-gray-400'}`}
                                />
                            </div>

                            <span className={`text-[10px] font-medium mt-1 transition-colors duration-300 ${isActive ? 'text-brand-orange' : 'text-gray-400'}`}>
                                {tab.label}
                            </span>

                            {isActive && (
                                <motion.div
                                    layoutId="nav-pill"
                                    className="absolute -top-3 w-8 h-1 bg-brand-orange rounded-b-lg shadow-lg shadow-orange-500/30"
                                    transition={{ type: "spring", stiffness: 300, damping: 30 }}
                                />
                            )}
                        </motion.button>
                    );
                })}
            </div>
        </div>
    );
}
