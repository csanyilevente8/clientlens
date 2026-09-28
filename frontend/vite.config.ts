import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Proxy API calls to the FastAPI backend so the browser can call "/api/..."
    // without CORS setup during local dev.
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
