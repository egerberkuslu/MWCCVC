/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["SF Pro Display", "SF Pro Text", "-apple-system", "BlinkMacSystemFont", "Helvetica Neue", "sans-serif"],
        mono: ["SF Mono", "Menlo", "Consolas", "monospace"],
      },
      borderRadius: {
        sm: "10px",
        md: "16px",
        lg: "22px",
        xl: "28px",
        pill: "999px",
      },
      animation: {
        "fade-in": "fade-in 300ms ease-out both",
        spin: "spin 1s linear infinite",
        "pulse-glow": "pulse-glow 1.5s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
