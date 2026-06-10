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
        /* legacy aliases — kept so existing class names continue to work */
        bg:               "var(--bg)",
        surface:          "var(--surface)",
        "surface-2":      "var(--surface-2)",
        "surface-3":      "var(--surface-3)",
        "border-default": "var(--border)",
        "cyan-brand":     "var(--cyan)",
        "green-brand":    "var(--green)",
        "red-brand":      "var(--red)",
        "amber-brand":    "var(--amber)",
        "purple-brand":   "var(--purple)",
        "text-primary":   "var(--text)",
        "text-muted":     "var(--text-2)",
        "text-subtle":    "var(--text-3)",
      },
      fontFamily: {
        mono: ["'JetBrains Mono'", "ui-monospace", "monospace"],
      },
      animation: {
        "border-pulse": "border-pulse 2.2s ease-in-out infinite",
        "fade-in":      "fade-in 0.2s ease-out",
        "slide-in":     "slide-in 0.2s ease-out",
        shimmer:        "shimmer 1.4s ease-in-out infinite",
      },
      keyframes: {
        "border-pulse": {
          "0%, 100%": { opacity: "0.35" },
          "50%":       { opacity: "1" },
        },
        "fade-in": {
          from: { opacity: "0" },
          to:   { opacity: "1" },
        },
        "slide-in": {
          from: { opacity: "0", transform: "translateY(-4px)" },
          to:   { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          from: { backgroundPosition: "-200% 0" },
          to:   { backgroundPosition:  "200% 0" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
