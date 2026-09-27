import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
export default defineConfig({
  plugins: [react()],
  server: {
    fs: {
      allow: [
        fileURLToPath(new URL(".", import.meta.url)),
        fileURLToPath(new URL("../content", import.meta.url)),
        fileURLToPath(new URL("../backend/src/fs/factory", import.meta.url)),
      ],
    },
    host: "localhost",
    port: 5173,
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    restoreMocks: true,
  },
});
