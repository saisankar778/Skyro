import React, { useContext } from 'react';
import { motion } from 'framer-motion';
import { User, Phone, MapPin, LogOut, ChevronRight, Shield, CreditCard, Heart, Settings } from 'lucide-react';
import { AppContext } from '../../context/AppContext';

export default function ProfileScreen() {
    const context = useContext(AppContext);

    // Attempt to get user info from localStorage or context
    // Since AppContext doesn't expose user object directly but getCurrentUserId, we use that + local storage
    const userPhone = localStorage.getItem('skyro_user');
    const isLoggedIn = !!userPhone;

    const handleLogout = () => {
        if (confirm('Are you sure you want to logout?')) {
            localStorage.removeItem('skyro_user');
            localStorage.removeItem('skyro_user_tokens');
            window.location.reload();
        }
    };

    const menuItems = [
        { icon: MapPin, label: 'Manage Addresses', subtitle: 'Home, Work, Other' },
        { icon: CreditCard, label: 'Payment Methods', subtitle: 'Cards, UPI, Wallets' },
        { icon: Heart, label: 'Favorites', subtitle: 'Restaurants & Orders' },
        { icon: Shield, label: 'Privacy & Security', subtitle: 'Password, Biometrics' },
        { icon: Settings, label: 'Settings', subtitle: 'Notifications, App Info' },
    ];

    return (
        <div className="min-h-full pb-20 bg-warm-bg">
            <div className="bg-white p-6 shadow-sm rounded-b-3xl">
                <div className="flex items-center gap-4 mb-4">
                    <div className="w-20 h-20 rounded-full bg-orange-100 flex items-center justify-center border-4 border-white shadow-lg">
                        <User size={40} className="text-brand-orange" />
                    </div>
                    <div>
                        <h2 className="text-2xl font-bold text-dark-text">
                            {isLoggedIn ? 'User' : 'Guest'}
                        </h2>
                        <p className="text-gray-500 font-medium">
                            {isLoggedIn ? (userPhone || 'Verified User') : 'Welcome to Skyro'}
                        </p>
                        {isLoggedIn && (
                            <div className="mt-1 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                                Verified
                            </div>
                        )}
                    </div>
                </div>
            </div>

            <div className="px-4 mt-6 space-y-4">
                <div className="bg-white rounded-2xl shadow-sm overflow-hidden">
                    {menuItems.map((item, index) => (
                        <button
                            key={index}
                            className="w-full flex items-center justify-between p-4 border-b border-gray-50 last:border-0 hover:bg-gray-50 transition-colors"
                        >
                            <div className="flex items-center gap-4">
                                <div className="w-10 h-10 rounded-full bg-gray-50 flex items-center justify-center text-gray-600">
                                    <item.icon size={20} />
                                </div>
                                <div className="text-left">
                                    <h3 className="font-semibold text-gray-800">{item.label}</h3>
                                    <p className="text-xs text-gray-500">{item.subtitle}</p>
                                </div>
                            </div>
                            <ChevronRight size={18} className="text-gray-400" />
                        </button>
                    ))}
                </div>

                <div className="bg-white rounded-2xl shadow-sm overflow-hidden">
                    <button
                        onClick={handleLogout}
                        className="w-full flex items-center gap-4 p-4 text-red-600 hover:bg-red-50 transition-colors"
                    >
                        <div className="w-10 h-10 rounded-full bg-red-50 flex items-center justify-center">
                            <LogOut size={20} />
                        </div>
                        <span className="font-semibold">Log Out</span>
                    </button>
                </div>

                <div className="text-center mt-8 text-gray-400 text-xs">
                    <p>Skyro Drone Delivery</p>
                    <p>v2.0.1 • Built with ❤️</p>
                </div>
            </div>
        </div>
    );
}
