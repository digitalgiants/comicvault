/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#fef3f2',
          100: '#fde8e5',
          500: '#e63b2e',
          600: '#cc2d21',
          700: '#a82318',
          900: '#7a1810',
        },
      },
    },
  },
  plugins: [],
}
