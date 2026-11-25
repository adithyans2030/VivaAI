import { fileURLToPath, URL } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  // Port 3000 is the origin the backend's CORS_ORIGINS allows by default.
  server: { port: 3000, strictPort: true },
  preview: { port: 3000, strictPort: true },
});
