import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../static",   // FastAPI serves this folder
    emptyOutDir: true,
  },
  server: {
    proxy: { "/api": "http://localhost:8000" }, // local dev -> FastAPI
  },
});
