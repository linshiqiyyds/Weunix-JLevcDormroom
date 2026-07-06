import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "PingFang SC", "Microsoft YaHei UI", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Cascadia Code", "Consolas", "monospace"],
      },
      colors: {
        ink: "#08090B",
        panel: "#0F1115",
        line: "rgba(255,255,255,0.1)",
        acid: "#DFFF4F",
        ion: "#7DD3FC",
        ember: "#FFB86B",
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(223,255,79,.14), 0 24px 90px rgba(0,0,0,.42)",
        lift: "0 18px 60px rgba(0,0,0,.28)",
      },
    },
  },
  plugins: [],
} satisfies Config;
