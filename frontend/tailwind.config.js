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
      }
    },
  },
  plugins: [],
}
