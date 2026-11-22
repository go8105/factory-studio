import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Two static pages: / (business card) and /hanjum/ (product page).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: { rollupOptions: { input: { main: "index.html", hanjum: "hanjum/index.html" } } },
});
