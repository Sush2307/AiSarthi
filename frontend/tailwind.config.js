/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'Manrope', 'system-ui', '-apple-system', 'sans-serif'],
        heading: ['Manrope', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      colors: {
        brand: {
          50: "#F2F7F4",
          100: "#E8F2EB",
          200: "#D0E3D6",
          300: "#A2C7B1",
          400: "#6DA486",
          500: "#3D8C6C",
          600: "#287D65",
          700: "#1C6B53",
          800: "#145C45",
          900: "#0D4232",
          950: "#07261C",
          DEFAULT: "#145C45",
        },
        ivory: {
          50: "#FAFBF7",
          100: "#F6F7F2",
          200: "#EDF0E8",
          300: "#E1E7DF",
          400: "#CED7CA",
          500: "#B4C1AF",
          DEFAULT: "#F6F7F2",
        },
        pine: {
          950: "#0D1814",
          900: "#172B24",
          800: "#243D34",
          700: "#375247",
          600: "#4D6359",
          500: "#66736B",
          400: "#88958D",
          300: "#B1BBB5",
          200: "#D7DDD9",
          100: "#EDF2EE",
          50: "#F5F8F6",
          DEFAULT: "#172B24",
        },
        night: {
          950: "#0A110E", // Deep dark canvas
          900: "#101A16", // Elevated dark header & surfaces
          850: "#16231E", // Dark card surface
          800: "#1D2D27", // Hover dark surface
          750: "#24362F", // Dividers
          700: "#2D3F37", // Dark borders
          600: "#3F554C",
          500: "#5D766C",
          400: "#829C91",
          300: "#ABC1B7",
          200: "#D5E2DC",
          100: "#EDF4F0",
        },
        alert: {
          warning: "#9A5B12",
          "warning-bg": "#FEF7EE",
          "warning-border": "#F8D8A8",
          error: "#B42318",
          "error-bg": "#FEF3F2",
          "error-border": "#FECDCA",
          success: "#20744A",
          "success-bg": "#EDF8F2",
          "success-border": "#BCE6CF",
        },
      },
      maxWidth: {
        'page': '1600px',
      },
      boxShadow: {
        subtle: "0 1px 2px 0 rgba(20, 92, 69, 0.04), 0 1px 3px 0 rgba(0, 0, 0, 0.02)",
        card: "0 2px 4px 0 rgba(20, 92, 69, 0.04), 0 1px 2px 0 rgba(0, 0, 0, 0.02)",
        elevated: "0 8px 16px -4px rgba(20, 92, 69, 0.08), 0 2px 4px -2px rgba(0, 0, 0, 0.02)",
      },
    },
  },
  plugins: [],
};
