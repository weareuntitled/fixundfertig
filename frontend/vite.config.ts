import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { TanStackRouterVite } from "@tanstack/router-vite-plugin";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  plugins: [
    tailwindcss(),
    react(),
    TanStackRouterVite({
      routesDirectory: "src/routes",
      generatedRouteTree: "src/routeTree.gen.ts",
    }),
  ],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  base: "/static/frontend/",
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: false },
      "/static": { target: "http://localhost:8000", changeOrigin: false },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test-setup.ts",
    exclude: ["**/node_modules/**", "**/dist/**", "e2e/**"],
  },
});
