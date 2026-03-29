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
        paper: {
          DEFAULT: "#faf9f6",
          warm:    "#f7f4ee",
          rule:    "#e2ddd4",
          rule2:   "#ece8e0",
        },
        ink: {
          DEFAULT:  "#1c1810",
          mid:      "#5a5040",
          faint:    "#a09080",
          faintest: "#cec8bc",
        },
        binding: "#2a2018",
        accent:  "#c0392b",
        "margin-red": "#e8b4b0",
        "col-story":   "#2d6a4f",
        "col-accept":  "#1e3a5f",
        "col-test":    "#6b3a2a",
        "col-release": "#5a3a7a",
        status: {
          met:     "#4a9e6b",
          partial: "#c4a35a",
          missing: "#c0392b",
          open:    "#1e3a5f",
        },
      },
      fontFamily: {
        serif:   ["'Lora'", "serif"],
        body:    ["'Crimson Pro'", "serif"],
        mono:    ["'JetBrains Mono'", "monospace"],
        heading: ["'Lora'", "serif"],
        sans:    ["Inter", "system-ui", "sans-serif"],
      },
      spacing: {
        "18":    "4.5rem",
        "22":    "5.5rem",
        sidebar: "200px",
        topbar:  "48px",
      },
      keyframes: {
        "ink-in": {
          "0%":   { opacity: "0", transform: "translateY(3px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          "0%":   { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "slide-in-left": {
          "0%":   { opacity: "0", transform: "translateX(-12px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
      },
      animation: {
        "ink-in":        "ink-in 0.18s ease both",
        "fade-in":       "fade-in 0.4s ease forwards",
        "slide-in-left": "slide-in-left 0.3s ease forwards",
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};

export default config;
