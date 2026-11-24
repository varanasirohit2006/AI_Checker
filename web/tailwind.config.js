/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        gltr: {
          green: "#22c55e",
          yellow: "#eab308",
          red: "#ef4444",
          purple: "#a855f7",
        },
      },
    },
  },
  plugins: [],
};
