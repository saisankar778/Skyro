/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './index.html',
    './index.tsx',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        'brand-orange': '#FF6A00',
        'brand-red': '#FF3B30',
        'offer-yellow': '#FFD400',
        'warm-bg': '#FFF7ED',
        'dark-text': '#1F2937',
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
