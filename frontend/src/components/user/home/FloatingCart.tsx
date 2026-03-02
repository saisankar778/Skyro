import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ShoppingBag, ChevronRight } from 'lucide-react';

type Props = {
    itemCount: number;
    totalPrice: number;
    onClick: () => void;
};

export default function FloatingCart({ itemCount, totalPrice, onClick }: Props) {
    return (
        <AnimatePresence>
            {itemCount > 0 && (
                <motion.div
                    initial={{ y: 100, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    exit={{ y: 100, opacity: 0 }}
                    className="fixed bottom-24 left-4 right-4 z-50 max-w-md mx-auto"
                >
                    <motion.button
                        onClick={onClick}
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        className="w-full bg-gradient-to-r from-brand-orange to-brand-red text-white p-4 rounded-2xl shadow-xl shadow-orange-500/30 flex items-center justify-between group"
                    >
                        <div className="flex items-center gap-3">
                            <div className="relative">
                                <div className="bg-white/20 p-2.5 rounded-xl backdrop-blur-sm">
                                    <ShoppingBag size={20} className="text-white" />
                                </div>
                                <span className="absolute -top-1 -right-1 bg-white text-brand-orange text-[10px] font-bold w-5 h-5 rounded-full flex items-center justify-center border-2 border-brand-orange">
                                    {itemCount}
                                </span>
                            </div>
                            <div className="flex flex-col items-start">
                                <span className="text-[10px] font-medium text-white/80 uppercase tracking-wide">Total</span>
                                <span className="text-lg font-bold">₹{totalPrice}</span>
                            </div>
                        </div>

                        <div className="flex items-center gap-2 pr-2">
                            <span className="text-sm font-bold opacity-90 group-hover:opacity-100 transition-opacity">View Cart</span>
                            <div className="bg-white/20 p-1.5 rounded-full backdrop-blur-sm group-hover:translate-x-1 transition-transform">
                                <ChevronRight size={16} />
                            </div>
                        </div>
                    </motion.button>
                </motion.div>
            )}
        </AnimatePresence>
    );
}
