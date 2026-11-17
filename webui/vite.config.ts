/// <reference types="vitest/config" />

import { readFileSync } from "node:fs";
import { fileURLToPath, URL } from "node:url";
import vue from "@vitejs/plugin-vue";
import { defineConfig, loadEnv } from "vite";

const pkg = JSON.parse(
  readFileSync(new URL("./package.json", import.meta.url), "utf-8"),
) as { version: string };

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const proxyTarget = env.VITE_API_PROXY || "http://127.0.0.1:8113";

  return {
    define: {
      __APP_VERSION__: JSON.stringify(pkg.version),
    },
    plugins: [vue()],
    resolve: {
      alias: {
        "@": fileURLToPath(new URL("./src", import.meta.url)),
      },
    },
    build: {
      outDir: fileURLToPath(new URL("../deluge_mobileui/data", import.meta.url)),
      emptyOutDir: true,
    },
    server: {
      proxy: {
        "/api": { target: proxyTarget, changeOrigin: true },
        "/health": { target: proxyTarget, changeOrigin: true },
      },
    },
    test: {
      environment: "happy-dom",
      include: ["src/**/*.spec.ts"],
      coverage: {
        provider: "v8",
        reporter: ["text", "lcov"],
        reportsDirectory: "coverage",
        include: ["src/**/*.ts"],
        exclude: ["src/**/*.spec.ts", "src/env.d.ts"],
        thresholds: {
          statements: 55,
          branches: 50,
          functions: 50,
          lines: 55,
        },
      },
    },
  };
});
