import React from 'react';
import { motion } from 'framer-motion';

export default function BannerCarousel() {
    return (
        <div className="px-4 py-2 overflow-hidden">
            <motion.div
                initial={{ scale: 0.95, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ delay: 0.2 }}
                className="relative rounded-[24px] bg-gradient-to-r from-brand-orange to-brand-red p-6 shadow-xl shadow-orange-500/20 overflow-hidden"
            >
                {/* Decorative Circles */}
                <div className="absolute top-0 right-0 w-32 h-32 bg-white/10 rounded-full blur-2xl -mr-10 -mt-10"></div>
                <div className="absolute bottom-0 left-0 w-24 h-24 bg-black/5 rounded-full blur-xl -ml-8 -mb-8"></div>

                <div className="relative z-10 flex justify-between items-center">
                    <div className="flex-1 pr-4">
                        <motion.div
                            initial={{ y: 20, opacity: 0 }}
                            animate={{ y: 0, opacity: 1 }}
                            transition={{ delay: 0.3 }}
                        >
                            <span className="inline-block bg-white/20 backdrop-blur-sm text-white text-[10px] font-bold px-2 py-1 rounded-md mb-2 border border-white/10">
                                LIMITED OFFER
                            </span>
                            <h3 className="text-white text-2xl font-black leading-tight mb-2 drop-shadow-sm">
                                Free Drone<br />Delivery Today
                            </h3>
                            <p className="text-white/90 text-xs font-medium mb-4 opacity-90">
                                Get food under 10 mins 🚁
                            </p>
                            <motion.button
                                whileTap={{ scale: 0.95 }}
                                className="bg-white text-brand-orange px-5 py-2.5 rounded-xl text-xs font-bold shadow-lg hover:bg-gray-50 transition-colors uppercase tracking-wide"
                            >
                                Order Now
                            </motion.button>
                        </motion.div>
                    </div>

                    {/* 3D-ish Image Container */}
                    <motion.div
                        animate={{ y: [0, -10, 0] }}
                        transition={{ repeat: Infinity, duration: 4, ease: "easeInOut" }}
                        className="w-32 h-32 relative flex-shrink-0"
                    >
                        <div className="absolute inset-0 bg-white/20 blur-xl rounded-full scale-75"></div>
                        {/* Using an emoji for now, but in real app use an image */}
                        <div className="w-full h-full flex items-center justify-center text-[5rem] drop-shadow-2xl filter contrast-125">
                            🍔
                        </div>
                    </motion.div>
                </div>
            </motion.div>
        </div>
    );
}
