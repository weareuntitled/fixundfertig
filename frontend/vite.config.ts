import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { TanStackRouterVite } from "@tanstack/router-vite-plugin";
import { fileURLToPath, URL } from "node:url";

const appRevision = process.env.VITE_APP_REVISION || "dev";

export default defineConfig({
  plugins: [
    {
      name: "app-revision",
      transformIndexHtml: (html) => html.replaceAll("%APP_REVISION%", appRevision),
    },
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
      "/static": {
        target: "http://localhost:8000",
        changeOrigin: false,
        bypass: (req) => {
          if (req.url?.startsWith("/static/frontend/")) {
            return req.url;
          }
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test-setup.ts",
    exclude: ["**/node_modules/**", "**/dist/**", "e2e/**"],
  },
});
