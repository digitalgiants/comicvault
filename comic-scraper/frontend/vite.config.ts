import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/lookup": "http://localhost:9095",
      "/health": "http://localhost:9095",
    },
  },
});
