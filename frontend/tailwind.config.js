/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: 'var(--bg)',
        surface: 'var(--surface)',
        text: 'var(--text)',
        muted: 'var(--muted)',
        primary: 'var(--primary)',
        'primary-contrast': 'var(--primary-contrast)',
        accent: 'var(--accent)',
        border: 'var(--border)',
      },
      boxShadow: {
        'glow': '0 0 10px var(--primary)',
        'card': '0 10px 30px var(--shadow)',
      },
      // *** CHANGED: Custom Keyframes and Animations added ***
      keyframes: {
        'subtle-spin': {
          '0%': { transform: 'rotate(0deg)' },
          '100%': { transform: 'rotate(360deg)' },
        },
        'pulse-glow': {
          '0%, 100%': { opacity: 0.8, transform: 'scale(1)' },
          '50%': { opacity: 1, transform: 'scale(1.1)' },
        },
        'slide-fade-in': {
          '0%': { opacity: 0, transform: 'translateY(-10px)' },
          '100%': { opacity: 1, transform: 'translateY(0)' },
        },
        'press-down': { // For connecting button click effect
          '0%, 100%': { transform: 'scale(1)' },
          '50%': { transform: 'scale(0.95)' },
        }
      },
      animation: {
        'subtle-spin': 'subtle-spin 15s linear infinite',
        'pulse-glow': 'pulse-glow 2s ease-in-out infinite',
        'slide-fade-in': 'slide-fade-in 1s ease-out forwards', // Changed duration to 1s
        'press-down': 'press-down 0.2s ease-out',
      }
      // *** END CHANGED ***
    },
  },
  plugins: [],
}