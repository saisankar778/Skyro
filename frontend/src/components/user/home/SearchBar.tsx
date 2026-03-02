import React from 'react';
import { motion } from 'framer-motion';
import { Search } from 'lucide-react';

type Props = {
    searchQuery: string;
    setSearchQuery: (query: string) => void;
};

export default function SearchBar({ searchQuery, setSearchQuery }: Props) {
    return (
        <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.1 }}
            className="px-4 py-3 bg-warm-bg"
        >
            <div className="relative group">
                <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none transition-colors group-focus-within:text-brand-orange text-gray-400">
                    <Search size={20} strokeWidth={2.5} />
                </div>
                <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="block w-full pl-12 pr-4 py-3.5 border-none rounded-2xl bg-white shadow-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-brand-orange/20 focus:shadow-lg transition-all duration-300 font-medium text-sm"
                    placeholder="Search for 'Biryani' or 'Pizza'"
                />
                <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
                    <span className="h-6 w-[1px] bg-gray-200 mx-2"></span>
                    <span className="text-gray-400">🎤</span>
                </div>
            </div>
        </motion.div>
    );
}
