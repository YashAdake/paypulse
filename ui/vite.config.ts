import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // `npm run dev` outside Docker: send API calls to a locally running api service.
  server: { proxy: { "/api": "http://localhost:8000" } },
});
