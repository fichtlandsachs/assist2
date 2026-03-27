import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#F5F0E8",
        surface: "#FFFFFF",
        foreground: "#0A0A0A",
        primary: {
          DEFAULT: "#FF5C00",
          foreground: "#0A0A0A",
        },
        secondary: {
          DEFAULT: "#FFD700",
          foreground: "#0A0A0A",
        },
        teal: {
          DEFAULT: "#00D4AA",
          foreground: "#0A0A0A",
        },
        muted: {
          DEFAULT: "#6B6B6B",
          foreground: "#6B6B6B",
        },
        border: "#0A0A0A",
        neo: {
          black: "#0A0A0A",
          orange: "#FF5C00",
          yellow: "#FFD700",
          teal: "#00D4AA",
          bg: "#F5F0E8",
          muted: "#6B6B6B",
        },
        status: {
          met: "#22C55E",
          partial: "#FFD700",
          missing: "#EF4444",
          open: "#FF5C00",
        },
      },
      fontFamily: {
        heading: ["Space Grotesk", "system-ui", "sans-serif"],
        body: ["Inter", "system-ui", "sans-serif"],
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      fontSize: {
        "display-xl": ["4.5rem", { lineHeight: "1.05", fontWeight: "800" }],
        "display-lg": ["3.5rem", { lineHeight: "1.1", fontWeight: "800" }],
        "display-md": ["2.5rem", { lineHeight: "1.15", fontWeight: "700" }],
        "display-sm": ["2rem", { lineHeight: "1.2", fontWeight: "700" }],
      },
      boxShadow: {
        neo: "4px 4px 0px #0A0A0A",
        "neo-sm": "2px 2px 0px #0A0A0A",
        "neo-lg": "6px 6px 0px #0A0A0A",
        "neo-orange": "4px 4px 0px #FF5C00",
        "neo-teal": "4px 4px 0px #00D4AA",
        "neo-yellow": "4px 4px 0px #FFD700",
        "neo-pressed": "1px 1px 0px #0A0A0A",
        none: "none",
      },
      borderWidth: {
        DEFAULT: "2px",
        "0": "0",
        "1": "1px",
        "2": "2px",
        "4": "4px",
      },
      spacing: {
        "18": "4.5rem",
        "22": "5.5rem",
        sidebar: "15rem",
      },
      keyframes: {
        "press-down": {
          "0%": { transform: "translate(0, 0)", boxShadow: "4px 4px 0px #0A0A0A" },
          "100%": { transform: "translate(2px, 2px)", boxShadow: "2px 2px 0px #0A0A0A" },
        },
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "slide-in-left": {
          "0%": { opacity: "0", transform: "translateX(-16px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
      },
      animation: {
        "press-down": "press-down 0.1s ease forwards",
        "fade-in": "fade-in 0.4s ease forwards",
        "slide-in-left": "slide-in-left 0.3s ease forwards",
      },
    },
  },
  plugins: [],
};

export default config;
