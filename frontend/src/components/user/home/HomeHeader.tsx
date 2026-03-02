import React from 'react';
import { motion } from 'framer-motion';

type Props = {
    location: string;
    onClickLocation: () => void;
};

export default function HomeHeader({ location, onClickLocation }: Props) {
    return (
        <motion.div
            initial={{ y: -50, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            className="sticky top-0 z-50 bg-warm-bg/95 backdrop-blur-md shadow-sm border-b border-orange-100/50"
        >
            <div className="px-4 py-3">
                <div className="flex items-center justify-between">
                    <div className="flex flex-col">
                        <div className="flex items-baseline gap-1.5 text-xs font-bold text-gray-500 tracking-wide uppercase">
                            <span className="text-brand-orange">📍</span> Delivering to
                        </div>
                        <div
                            onClick={onClickLocation}
                            className="flex items-center gap-1 group cursor-pointer"
                        >
                            <h2 className="text-base font-bold text-dark-text truncate max-w-[200px] border-b-2 border-dashed border-gray-300 group-hover:border-brand-orange transition-colors">
                                {location}
                            </h2>
                            <motion.svg
                                whileHover={{ rotate: 180 }}
                                className="w-4 h-4 text-brand-orange"
                                fill="none"
                                stroke="currentColor"
                                viewBox="0 0 24 24"
                            >
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 9l-7 7-7-7" />
                            </motion.svg>
                        </div>
                    </div>

                    <motion.div
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.95 }}
                        className="relative"
                    >
                        <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-brand-orange to-brand-red p-[2px] shadow-lg shadow-orange-500/20">
                            <div className="w-full h-full rounded-full bg-white flex items-center justify-center overflow-hidden">
                                <span className="text-brand-orange font-bold text-lg">S</span>
                            </div>
                        </div>
                        <span className="absolute top-0 right-0 w-3 h-3 bg-green-500 border-2 border-white rounded-full"></span>
                    </motion.div>
                </div>

                <div className="mt-2 flex items-center justify-between">
                    <p className="text-[10px] font-semibold text-brand-orange bg-orange-50 px-2 py-0.5 rounded-full inline-flex items-center gap-1">
                        <span>🚁</span> Fastest Delivery
                    </p>
                    <p className="text-[10px] text-gray-400 font-medium">12 mins to you</p>
                </div>
            </div>
        </motion.div>
    );
}
