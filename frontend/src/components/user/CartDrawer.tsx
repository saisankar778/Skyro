import React from 'react';
import { motion } from 'framer-motion';
import { Minus, Plus, X, ChevronRight, ShoppingBag } from 'lucide-react';
import type { CartItem, MenuItem } from '../../types';

type Props = {
    cart: CartItem[];
    onBack: () => void;
    onAddItem: (item: MenuItem) => void;
    onRemoveItem: (itemId: string) => void;
    onCheckout: () => void;
};

export default function CartDrawer({ cart, onBack, onAddItem, onRemoveItem, onCheckout }: Props) {
    const cartTotal = cart.reduce((sum, item) => sum + item.price * item.quantity, 0);
    const deliveryFee = 20;
    const platformFee = 5;
    const grandTotal = cartTotal + deliveryFee + platformFee;

    return (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 backdrop-blur-sm">
            <motion.div
                initial={{ y: '100%' }}
                animate={{ y: 0 }}
                exit={{ y: '100%' }}
                transition={{ type: 'spring', damping: 25, stiffness: 200 }}
                className="w-full max-w-md bg-warm-bg rounded-t-[30px] overflow-hidden max-h-[90vh] flex flex-col shadow-2xl"
            >
                {/* Header */}
                <div className="px-6 py-5 border-b border-gray-100 bg-white flex items-center justify-between sticky top-0 z-10">
                    <div className="flex items-center gap-3">
                        <div className="bg-brand-orange/10 p-2 rounded-xl">
                            <ShoppingBag size={20} className="text-brand-orange" />
                        </div>
                        <div>
                            <h2 className="text-lg font-bold text-dark-text">Your Cart</h2>
                            <p className="text-xs text-gray-400 font-medium whitespace-nowrap overflow-hidden text-ellipsis">
                                {cart.length} items from {cart[0]?.name ? 'Restaurant' : 'Selection'}
                            </p>
                        </div>
                    </div>
                    <button
                        onClick={onBack}
                        className="p-2 bg-gray-50 rounded-full hover:bg-gray-100 transition-colors"
                    >
                        <X size={20} className="text-gray-500" />
                    </button>
                </div>

                {/* Scrollable Content */}
                <div className="overflow-y-auto flex-1 p-6 space-y-6">
                    {cart.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-full py-10 opacity-50">
                            <ShoppingBag size={48} className="text-gray-300 mb-4" />
                            <p className="text-gray-500 font-medium">Your cart is empty</p>
                            <button onClick={onBack} className="mt-4 text-brand-orange font-bold text-sm">Browse Restaurants</button>
                        </div>
                    ) : (
                        <>
                            {/* Items List */}
                            <div className="space-y-4 bg-white p-4 rounded-2xl shadow-sm border border-gray-100">
                                {cart.map((item) => (
                                    <div key={item.id} className="flex items-center justify-between">
                                        <div className="flex items-start gap-3">
                                            <div className={`mt-1 w-4 h-4 border-2 flex items-center justify-center rounded-sm ${item.name.includes('Chicken') ? 'border-red-500' : 'border-green-600'}`}>
                                                <div className={`w-2 h-2 rounded-full ${item.name.includes('Chicken') ? 'bg-red-500' : 'bg-green-600'}`}></div>
                                            </div>
                                            <div>
                                                <h4 className="text-sm font-semibold text-gray-800 w-32 truncate">{item.name}</h4>
                                                <p className="text-xs text-gray-500">₹{item.price * item.quantity}</p>
                                            </div>
                                        </div>

                                        <div className="flex items-center border border-gray-200 rounded-lg bg-gray-50">
                                            <button
                                                onClick={() => onRemoveItem(item.id)}
                                                className="p-1 px-2 text-gray-500 hover:text-red-500 font-bold"
                                            >
                                                <Minus size={14} />
                                            </button>
                                            <span className="text-xs font-bold w-4 text-center">{item.quantity}</span>
                                            <button
                                                onClick={() => onAddItem(item)}
                                                className="p-1 px-2 text-green-600 hover:text-green-700 font-bold"
                                            >
                                                <Plus size={14} />
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            </div>

                            {/* Bill Details */}
                            <div className="bg-white p-4 rounded-2xl shadow-sm border border-gray-100 space-y-2">
                                <h3 className="text-sm font-bold text-gray-800 mb-3">Bill Details</h3>
                                <div className="flex justify-between text-xs text-gray-500">
                                    <span>Item Total</span>
                                    <span>₹{cartTotal}</span>
                                </div>
                                <div className="flex justify-between text-xs text-gray-500">
                                    <span>Delivery Fee</span>
                                    <span className="text-green-600 font-medium">Free (Drone)</span>
                                </div>
                                <div className="flex justify-between text-xs text-gray-500">
                                    <span>Platform Fee</span>
                                    <span>₹{platformFee}</span>
                                </div>
                                <div className="flex justify-between text-xs text-gray-500">
                                    <span>Govt Taxes & Charges</span>
                                    <span>₹{Math.round(cartTotal * 0.05)}</span>
                                </div>
                                <div className="border-t border-dashed border-gray-200 my-2 pt-2 flex justify-between text-sm font-bold text-gray-900">
                                    <span>To Pay</span>
                                    <span>₹{cartTotal + platformFee + Math.round(cartTotal * 0.05)}</span>
                                </div>
                            </div>

                            {/* Delivery Instructions */}
                            <div className="bg-white p-4 rounded-2xl shadow-sm border border-gray-100">
                                <h3 className="text-sm font-bold text-gray-800 mb-2">Delivery Instructions</h3>
                                <div className="flex gap-2 overflow-x-auto scrollbar-hide pb-2">
                                    {['Avoid calling', 'Leave at door', 'Directions'].map(inst => (
                                        <button key={inst} className="flex-shrink-0 px-3 py-1.5 border border-gray-200 rounded-lg text-xs text-gray-600 hover:bg-gray-50 hover:border-brand-orange transition-colors">
                                            {inst}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        </>
                    )}
                </div>

                {/* Footer Actions */}
                {cart.length > 0 && (
                    <div className="p-4 bg-white border-t border-gray-100 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.05)]">
                        <button
                            onClick={onCheckout}
                            className="w-full bg-gradient-to-r from-green-600 to-green-500 text-white p-4 rounded-xl font-bold shadow-lg shadow-green-500/20 flex items-center justify-between group active:scale-[0.98] transition-all"
                        >
                            <div className="flex flex-col items-start">
                                <span className="text-[10px] font-medium opacity-80 uppercase tracking-wide">Total</span>
                                <span className="text-lg">₹{cartTotal + platformFee + Math.round(cartTotal * 0.05)}</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <span>Proceed to Pay</span>
                                <ChevronRight size={18} className="group-hover:translate-x-1 transition-transform" />
                            </div>
                        </button>
                    </div>
                )}
            </motion.div>
        </div>
    );
}
