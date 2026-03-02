import React, { useContext, useMemo } from 'react';
import { motion } from 'framer-motion';
import { ShoppingBag, Clock, CheckCircle2, XCircle, ChevronRight, Package, Truck, ArrowRight } from 'lucide-react';
import { AppContext } from '../../context/AppContext';
import { OrderStatus, Order } from '../../types';
import { RESTAURANTS } from '../../constants';

const STATUS_COLORS: Record<OrderStatus, string> = {
    [OrderStatus.PLACED]: 'text-blue-600 bg-blue-50',
    [OrderStatus.ACCEPTED]: 'text-indigo-600 bg-indigo-50',
    [OrderStatus.COOKING]: 'text-orange-600 bg-orange-50',
    [OrderStatus.READY_FOR_LAUNCH]: 'text-purple-600 bg-purple-50',
    [OrderStatus.EN_ROUTE]: 'text-amber-600 bg-amber-50',
    [OrderStatus.DELIVERED]: 'text-green-600 bg-green-50',
    [OrderStatus.FAILED]: 'text-red-600 bg-red-50',
    [OrderStatus.DECLINED]: 'text-gray-600 bg-gray-50',
};

const STATUS_LABELS: Record<OrderStatus, string> = {
    [OrderStatus.PLACED]: 'Order Placed',
    [OrderStatus.ACCEPTED]: 'Accepted',
    [OrderStatus.COOKING]: 'Preparing',
    [OrderStatus.READY_FOR_LAUNCH]: 'Ready for Pickup',
    [OrderStatus.EN_ROUTE]: 'Drone En Route',
    [OrderStatus.DELIVERED]: 'Delivered',
    [OrderStatus.FAILED]: 'Cancelled',
    [OrderStatus.DECLINED]: 'Declined',
};

type Props = {
    onTrackOrder?: (orderId: string) => void;
};

export default function OrdersScreen({ onTrackOrder }: Props) {
    const context = useContext(AppContext);

    // Get current user ID from local storage as AppContext doesn't expose it directly in a reactive way usually
    // But we know AppContext has getCurrentUserId internally. For now, we'll read from localStorage.
    const currentUserId = localStorage.getItem('skyro_user');

    const userOrders = useMemo(() => {
        if (!context?.orders) return [];
        // Filter orders for the current user (if logged in)
        // If no user is logged in (demo/guest), maybe show local orders or empty?
        // Let's show all local orders if userId matches or if we're in a "demo" flow where user might be implicit
        if (!currentUserId) return [];
        return context.orders
            .filter(order => order.user === currentUserId)
            .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
    }, [context?.orders, currentUserId]);

    if (!currentUserId) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-6">
                <div className="w-20 h-20 bg-gray-100 rounded-full flex items-center justify-center mb-4">
                    <ShoppingBag size={32} className="text-gray-400" />
                </div>
                <h3 className="text-lg font-bold text-gray-800">No Orders Yet</h3>
                <p className="text-gray-500 mt-2">Log in to see your past orders and track active deliveries.</p>
            </div>
        );
    }

    if (userOrders.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-6">
                <div className="w-20 h-20 bg-orange-50 rounded-full flex items-center justify-center mb-4">
                    <ShoppingBag size={32} className="text-orange-300" />
                </div>
                <h3 className="text-lg font-bold text-gray-800">Hungry?</h3>
                <p className="text-gray-500 mt-2">You haven't placed any orders yet. Explore restaurants near you!</p>
            </div>
        );
    }

    return (
        <div className="min-h-full pb-24 bg-warm-bg px-4 pt-4">
            <h2 className="text-2xl font-bold text-dark-text mb-6">Your Orders</h2>

            <div className="space-y-4">
                {userOrders.map((order) => {
                    const restaurant = RESTAURANTS.find(r => r.id === order.restaurantId);
                    const itemCount = order.items.reduce((acc, item) => acc + item.quantity, 0);
                    const isActive = [OrderStatus.PLACED, OrderStatus.ACCEPTED, OrderStatus.COOKING, OrderStatus.READY_FOR_LAUNCH, OrderStatus.EN_ROUTE].includes(order.status);

                    return (
                        <motion.div
                            key={order.id}
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100"
                        >
                            <div className="flex justify-between items-start mb-3">
                                <div>
                                    <h3 className="font-bold text-gray-800 text-lg">
                                        {restaurant?.name || 'Unknown Restaurant'}
                                    </h3>
                                    <p className="text-xs text-gray-500">
                                        {new Date(order.createdAt).toLocaleDateString()} • {new Date(order.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                    </p>
                                </div>
                                <div className={`px-3 py-1 rounded-full text-xs font-bold flex items-center gap-1 ${STATUS_COLORS[order.status] || 'bg-gray-100 text-gray-600'}`}>
                                    {isActive && <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse"></span>}
                                    {STATUS_LABELS[order.status] || order.status}
                                </div>
                            </div>

                            <div className="border-t border-b border-gray-50 py-3 mb-3 space-y-1">
                                {order.items.map((item, idx) => (
                                    <div key={idx} className="flex justify-between text-sm">
                                        <span className="text-gray-600">
                                            <span className="font-semibold text-gray-800">{item.quantity}x</span> {item.name}
                                        </span>
                                        <span className="text-gray-500">₹{item.price * item.quantity}</span>
                                    </div>
                                ))}
                            </div>

                            <div className="flex items-center justify-between">
                                <p className="text-sm font-bold text-gray-800">
                                    Total: <span className="text-lg">₹{order.total}</span>
                                </p>

                                {isActive ? (
                                    <button
                                        onClick={() => onTrackOrder?.(order.id)}
                                        className="flex items-center gap-1 text-xs font-bold text-brand-orange bg-orange-50 px-3 py-2 rounded-lg hover:bg-orange-100 transition-colors"
                                    >
                                        Track Order <ArrowRight size={14} />
                                    </button>
                                ) : (
                                    <button className="flex items-center gap-1 text-xs font-semibold text-gray-500 hover:text-gray-800 transition-colors">
                                        Reorder
                                    </button>
                                )}
                            </div>
                        </motion.div>
                    );
                })}
            </div>
        </div>
    );
}
