import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "#0a0e1a",
        surface: "#111827",
        "surface-2": "#1a2235",
        "border-default": "#1f2937",
        "cyan-brand": "#06b6d4",
        "green-brand": "#10b981",
        "red-brand": "#ef4444",
        "amber-brand": "#f59e0b",
        "purple-brand": "#8b5cf6",
        "text-primary": "#f9fafb",
        "text-muted": "#6b7280",
      },
      fontFamily: {
        mono: ["'JetBrains Mono'", "ui-monospace", "monospace"],
      },
      animation: {
        "border-pulse": "border-pulse 2s ease-in-out infinite",
        "fade-in": "fade-in 0.3s ease-out",
        "slide-in": "slide-in 0.2s ease-out",
      },
      keyframes: {
        "border-pulse": {
          "0%, 100%": { borderColor: "rgba(6,182,212,0.2)" },
          "50%": { borderColor: "rgba(6,182,212,0.6)" },
        },
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "slide-in": {
          from: { opacity: "0", transform: "translateY(-4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
