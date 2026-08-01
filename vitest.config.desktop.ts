/// <reference types="vitest" />
import { defineConfig } from "vitest/config";
import path from "path";
import { resolveAppRoot } from "./test_support/repoRoots";

const DESKTOP_WEB = path.join(resolveAppRoot(), "web");

export default defineConfig({
  resolve: {
    alias: {
      "@": path.join(DESKTOP_WEB, "src"),
      react: path.resolve(__dirname, "node_modules/react"),
      "react-dom": path.resolve(__dirname, "node_modules/react-dom"),
      "lucide-react": path.resolve(__dirname, "node_modules/lucide-react"),
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
