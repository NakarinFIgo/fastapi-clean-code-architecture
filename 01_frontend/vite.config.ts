import react from "@vitejs/plugin-react";
import { loadEnv } from "vite";
import { defineConfig } from "vitest/config";

// FastAPI serves the build at /ui, so assets must be requested from /ui/.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");

  return {
    base: "/ui/",
    plugins: [react()],
    server: {
      port: 5173,
      // `npm run dev`: same-origin calls to the API, no CORS setup needed.
      proxy: { "/api": env.VITE_API_PROXY_TARGET ?? "http://127.0.0.1:3000" },
    },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: ["./src/test/setup.ts"],
      css: false,
      // Tests do not need a local .env; MSW handlers match */api/v1/*.
      env: { VITE_API_BASE_URL: "/api/v1" },
    },
  };
});
