/** @type {import('tailwindcss').Config} */
export default {
  // Scan all TypeScript and TSX files for class names
  content: [
    "./index.html",
    "./src/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
