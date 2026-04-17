/// <reference types="vitest" />
import { defineConfig } from "vitest/config";
import path from "path";

const SERVER_WEB = path.resolve(
  __dirname,
  "..",
  "..",
  "MasterplanOptimiserV3 - Server",
  "MasterplanOptimiserV3---Server",
  "web",
);

export default defineConfig({
  resolve: {
    alias: {
      "@": path.join(SERVER_WEB, "src"),
      react: path.resolve(__dirname, "node_modules/react"),
      "react-dom": path.resolve(__dirname, "node_modules/react-dom"),
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    include: ["server_frontend/**/*.test.{ts,tsx}"],
    setupFiles: ["./vitest.setup.ts"],
    css: false,
  },
});
