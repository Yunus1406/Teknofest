import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: "#F6F7F5",
        ink: "#13221E",
        petrol: {
          DEFAULT: "#0F4A4D",
          dark: "#0B3638",
        },
        virgin: "#C97A3D",
        pcr: "#3E8F63",
        regranul: "#8A8F82",
        warn: "#B23A48",
      },
      fontFamily: {
        heading: ["var(--font-space-grotesk)", "sans-serif"],
        body: ["var(--font-ibm-plex-sans)", "sans-serif"],
        mono: ["var(--font-ibm-plex-mono)", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
