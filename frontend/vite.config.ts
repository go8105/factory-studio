import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// FS-009는 빌드 기반만 검증한다. 포털 진입 화면은 FS-017에서 작성한다.
export default defineConfig({
  plugins: [react()],
  build: {
    lib: {
      entry: "src/app/index.ts",
      formats: ["es"],
      fileName: "factory-studio",
    },
  },
});
