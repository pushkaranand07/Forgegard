import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Dev: `npm run dev` on :5173 proxies API calls to Django on :8000.
// Django build: output goes to Django's static dir and is served by api.views.spa.
// Vercel build: output goes to `dist/` with root base `/` as expected by Vercel.
const isVercel = Boolean(process.env.VERCEL);

export default defineConfig(({ command }) => ({
  plugins: [react(), tailwindcss()],
  base: isVercel ? "/" : command === "build" ? "/static/app/" : "/",
  build: {
    outDir: isVercel ? "dist" : "../frontend/static/app",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
}));
