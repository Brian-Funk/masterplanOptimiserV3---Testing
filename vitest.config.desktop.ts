/// <reference types="vitest" />
import { defineConfig } from "vitest/config";
import path from "path";

const DESKTOP_WEB = path.resolve(
  __dirname,
  "..",
  "..",
  "MasterplanOptimiserV3 - App",
  "masterplanOptimiserV3 - App",
  "web",
);

export default defineConfig({
  esbuild: {
    jsx: "automatic",
    jsxImportSource: "react",
  },
  resolve: {
    alias: {
      "@": path.join(DESKTOP_WEB, "src"),
      react: path.resolve(__dirname, "node_modules/react"),
      "react-dom": path.resolve(__dirname, "node_modules/react-dom"),
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    include: ["desktop_frontend/**/*.test.{ts,tsx}"],
    setupFiles: ["./vitest.setup.ts"],
    css: false,
  },
});
