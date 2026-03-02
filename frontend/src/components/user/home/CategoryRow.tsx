import React from 'react';
import { motion } from 'framer-motion';

type Category = {
    id: string;
    name: string;
    icon: string;
};

const categories: Category[] = [
    { id: 'pizza', name: 'Pizza', icon: '🍕' },
    { id: 'biryani', name: 'Biryani', icon: '🍛' },
    { id: 'burger', name: 'Burger', icon: '🍔' },
    { id: 'healthy', name: 'Healthy', icon: '🥗' },
    { id: 'offers', name: 'Offers', icon: '🎁' },
    { id: 'desserts', name: 'Desserts', icon: '🍰' },
];

type Props = {
    selectedCategory: string;
    setSelectedCategory: (id: string) => void;
};

export default function CategoryRow({ selectedCategory, setSelectedCategory }: Props) {
    return (
        <div className="py-6">
            <div className="px-4 mb-3 flex items-center justify-between">
                <h3 className="font-bold text-lg text-dark-text">What's on your mind?</h3>
            </div>

            <div className="flex gap-4 overflow-x-auto px-4 pb-4 scrollbar-hide snap-x">
                {categories.map((category, index) => (
                    <motion.button
                        key={category.id}
                        initial={{ opacity: 0, x: 20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.1 * index }}
                        onClick={() => setSelectedCategory(category.id)}
                        className="flex flex-col items-center min-w-[72px] snap-center group"
                    >
                        <div
                            className={`w-[72px] h-[72px] rounded-full flex items-center justify-center text-3xl shadow-sm transition-all duration-300 relative overflow-hidden ${selectedCategory === category.id
                                    ? 'bg-brand-orange shadow-brand-orange/30 ring-2 ring-offset-2 ring-brand-orange text-white'
                                    : 'bg-white hover:bg-orange-50 text-gray-700'
                                }`}
                        >
                            <span className={`transform transition-transform duration-300 ${selectedCategory === category.id ? 'scale-110' : 'group-hover:scale-110'}`}>
                                {category.icon}
                            </span>

                            {selectedCategory === category.id && (
                                <motion.div
                                    layoutId="activeCategory"
                                    className="absolute inset-0 bg-white/10"
                                />
                            )}
                        </div>
                        <span className={`text-xs mt-2 font-medium transition-colors ${selectedCategory === category.id ? 'text-brand-orange font-bold' : 'text-gray-600'
                            }`}>
                            {category.name}
                        </span>
                    </motion.button>
                ))}
            </div>
        </div>
    );
}
