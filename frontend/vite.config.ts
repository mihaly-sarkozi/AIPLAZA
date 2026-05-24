/// <reference types="vitest" />

import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const proxyTarget = env.VITE_DEV_PROXY_TARGET || "http://127.0.0.1:8001";
  const tenantDomain = env.VITE_TENANT_DOMAIN || "lvh.me";

  return {
    plugins: [react()],
    resolve: {
      alias: {
        "@frontend": fileURLToPath(new URL("./src", import.meta.url)),
        "@apps": fileURLToPath(new URL("../backend/apps", import.meta.url)),
      },
    },

    server: {
      port: 5173,
      host: true,
      strictPort: true,
      allowedHosts: [`.${tenantDomain}`, "localhost", "frontend"],
      watch: {
        ignored: [
          "**/.git/**",
          "**/.cursor/**",
          "**/.pytest_cache/**",
          "**/.ruff_cache/**",
          "**/.mypy_cache/**",
          "**/__pycache__/**",
          "**/.venv/**",
          "**/venv/**",
          "**/node_modules/**",
          "**/dist/**",
          "**/build/**",
          "**/coverage/**",
          "**/uploads/**",
          "**/agent-transcripts/**",
        ],
        interval: 500,
      },
      fs: {
        allow: [".."],
      },

      proxy: {
        "/api": {
          target: proxyTarget,
          changeOrigin: false,
          secure: false,
        },
      },
    },
    test: {
      environment: "jsdom",
      setupFiles: "./src/test/setup.ts",
      globals: true,
      exclude: ["node_modules/**", "dist/**", "e2e/**"],
    },
  };
});