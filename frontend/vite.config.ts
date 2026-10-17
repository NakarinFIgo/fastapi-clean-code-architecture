import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// FastAPI serves the build at /ui, so assets must be requested from /ui/.
export default defineConfig({
  base: "/ui/",
  plugins: [react()],
  server: {
    port: 5173,
    // `npm run dev`: same-origin calls to the API, no CORS setup needed.
    proxy: { "/api": "http://127.0.0.1:3000" },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
