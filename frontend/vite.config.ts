import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: {
    // Match the TS path alias "@/..." -> "src/..." so Vite can resolve it too.
    // (tsconfig "paths" only configures the type-checker, not the bundler.)
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  server: {
    port: 5173,
    // Proxy API calls to the FastAPI backend so the browser can call "/api/..."
    // without CORS setup during local dev.
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
