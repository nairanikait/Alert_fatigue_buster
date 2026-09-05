import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: "0.0.0.0",
    proxy: {
      "/api/ws": {
        target: "ws://localhost:8000",
        ws: true
      },
      "/ws": {
        target: "ws://localhost:8000",
        ws: true
      },
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true
      },
      "/health": {
        target: "http://localhost:8000",
        changeOrigin: true
      },
      "/docs": {
        target: "http://localhost:8000",
        changeOrigin: true
      },
      "/openapi.json": {
        target: "http://localhost:8000",
        changeOrigin: true
      }
    }
  }
});
