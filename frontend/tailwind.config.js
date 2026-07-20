/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          DEFAULT: '#003d7a',
          deep: '#00274d',
          mid: '#004f9a',
          h: '#0057ab',
        },
        teal: '#00bceb',
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      boxShadow: {
        sw: '0 1px 3px rgba(0,0,0,.07), 0 1px 2px rgba(0,0,0,.04)',
        swm: '0 4px 12px rgba(0,0,0,.08), 0 2px 4px rgba(0,0,0,.04)',
        swl: '0 16px 40px rgba(0,0,0,.12), 0 6px 12px rgba(0,0,0,.06)',
      }
    },
  },
  plugins: [],
}
