import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          primary: "#040c1a",
          secondary: "#070e1d",
          card: "#0b1525",
          elevated: "#0e1b2e",
          border: "#162035",
          "border-bright": "#1e2f4a",
        },
        accent: {
          cyan: "#00d4ff",
          "cyan-dim": "#009bbf",
          "cyan-bright": "#33ddff",
          blue: "#2563eb",
          "blue-dim": "#1e4db7",
          green: "#00e87a",
          "green-dim": "#00b85f",
          red: "#ff2d55",
          "red-dim": "#cc2444",
          amber: "#f59e0b",
          purple: "#7c3aed",
          "purple-bright": "#9d5cf6",
          gold: "#fbbf24",
          // Malaysian flag accents
          "my-red": "#CC0001",
          "my-blue": "#003399",
        },
        text: {
          primary: "#e8edf5",
          secondary: "#8fa3bb",
          muted: "#4a5f7a",
          accent: "#00d4ff",
          dim: "#2d3f55",
        },
        threat: {
          critical: "#ff2d55",
          high: "#f97316",
          medium: "#f59e0b",
          low: "#00e87a",
        },
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Fira Code", "Consolas", "monospace"],
        sans: ["Inter", "system-ui", "sans-serif"],
        display: ["Inter", "system-ui", "sans-serif"],
      },
      backgroundImage: {
        "grid-pattern":
          "linear-gradient(rgba(0,212,255,0.025) 1px, transparent 1px), linear-gradient(90deg, rgba(0,212,255,0.025) 1px, transparent 1px)",
        "grid-fine":
          "linear-gradient(rgba(0,212,255,0.015) 1px, transparent 1px), linear-gradient(90deg, rgba(0,212,255,0.015) 1px, transparent 1px)",
        "gradient-radial": "radial-gradient(var(--tw-gradient-stops))",
        "card-glow": "linear-gradient(135deg, rgba(0,212,255,0.06) 0%, transparent 60%)",
        "card-glow-red": "linear-gradient(135deg, rgba(255,45,85,0.06) 0%, transparent 60%)",
        "card-glow-green": "linear-gradient(135deg, rgba(0,232,122,0.06) 0%, transparent 60%)",
        "sidebar-active": "linear-gradient(90deg, rgba(0,212,255,0.15) 0%, rgba(0,212,255,0.03) 100%)",
        "hero-gradient": "linear-gradient(180deg, rgba(0,212,255,0.05) 0%, transparent 100%)",
        "shine": "linear-gradient(105deg, transparent 40%, rgba(255,255,255,0.04) 50%, transparent 60%)",
      },
      backgroundSize: {
        "grid": "40px 40px",
        "grid-fine": "16px 16px",
      },
      boxShadow: {
        "glow-cyan": "0 0 24px rgba(0,212,255,0.18), 0 0 48px rgba(0,212,255,0.06)",
        "glow-cyan-sm": "0 0 12px rgba(0,212,255,0.2)",
        "glow-red": "0 0 24px rgba(255,45,85,0.25), 0 0 48px rgba(255,45,85,0.08)",
        "glow-red-sm": "0 0 12px rgba(255,45,85,0.2)",
        "glow-green": "0 0 24px rgba(0,232,122,0.18)",
        "glow-green-sm": "0 0 12px rgba(0,232,122,0.18)",
        "card": "0 4px 32px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.04)",
        "card-hover": "0 8px 40px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.06)",
        "panel": "0 2px 16px rgba(0,0,0,0.4)",
        "inner-top": "inset 0 1px 0 rgba(255,255,255,0.05)",
      },
      animation: {
        "pulse-slow": "pulse 3s ease-in-out infinite",
        "pulse-fast": "pulse 1s ease-in-out infinite",
        "scan": "scan 2.5s linear infinite",
        "fade-in": "fadeIn 0.4s ease-out",
        "fade-up": "fadeUp 0.4s ease-out",
        "slide-right": "slideRight 0.3s ease-out",
        "blink": "blink 1s step-end infinite",
        "glow-pulse": "glowPulse 2.5s ease-in-out infinite alternate",
        "shimmer": "shimmer 2s linear infinite",
        "float": "float 6s ease-in-out infinite",
        "spin-slow": "spin 8s linear infinite",
        "border-glow": "borderGlow 2s ease-in-out infinite alternate",
        "count-up": "countUp 0.6s ease-out",
        "enter": "enter 0.3s ease-out",
      },
      keyframes: {
        scan: {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100vh)" },
        },
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        fadeUp: {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        slideRight: {
          "0%": { opacity: "0", transform: "translateX(-8px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        blink: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0" },
        },
        glowPulse: {
          "0%": { boxShadow: "0 0 5px rgba(0,212,255,0.1), 0 0 10px rgba(0,212,255,0.05)" },
          "100%": { boxShadow: "0 0 20px rgba(0,212,255,0.3), 0 0 40px rgba(0,212,255,0.1)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-6px)" },
        },
        borderGlow: {
          "0%": { borderColor: "rgba(0,212,255,0.2)" },
          "100%": { borderColor: "rgba(0,212,255,0.6)" },
        },
        countUp: {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        enter: {
          "0%": { opacity: "0", transform: "scale(0.97) translateY(4px)" },
          "100%": { opacity: "1", transform: "scale(1) translateY(0)" },
        },
      },
      transitionDuration: {
        "400": "400ms",
        "600": "600ms",
      },
    },
  },
  plugins: [],
};

export default config;
