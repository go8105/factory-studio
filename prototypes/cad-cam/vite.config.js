import { cpSync } from "node:fs";
import { defineConfig } from "vite";
export default defineConfig({
  publicDir: false,
  plugins: [
    {
      name: "cad-kernel-notices",
      closeBundle() {
        cpSync("licenses", "dist/licenses", { recursive: true });
      },
    },
  ],
  build: {
    rollupOptions: { input: { main: "index.html", part: "part-design.html" } },
  },
});
