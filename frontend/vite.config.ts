import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { setDefaultResultOrder } from "node:dns";
import { Agent } from "node:http";

// Node의 DNS 순서에 따라 Vite가 접속 주소를 127.0.0.1로 바꾸지 않게 한다.
setDefaultResultOrder("verbatim");
export default defineConfig({
  plugins: [
    react(),
    {
      name: "local-canonical-host",
      configureServer(server) {
        server.middlewares.use((request, response, next) => {
          if (/^127\.0\.0\.1(?::\d+)?$/.test(request.headers.host ?? "")) {
            response.statusCode = 307;
            response.setHeader(
              "Location",
              `http://localhost:${server.config.server.port}${request.url?.startsWith("/") ? request.url : "/"}`,
            );
            response.end();
            return;
          }
          next();
        });
      },
    },
  ],
  server: {
    fs: {
      allow: [
        fileURLToPath(new URL(".", import.meta.url)),
        fileURLToPath(new URL("../content", import.meta.url)),
        fileURLToPath(new URL("../backend/src/fs/factory", import.meta.url)),
        fileURLToPath(
          new URL("../backend/src/fs/core/menu_catalog.json", import.meta.url),
        ),
      ],
    },
    host: "localhost",
    port: Number(process.env.FS_SMOKE_WEB_PORT ?? 5173),
    strictPort: true,
    proxy: {
      "/api": {
        target: `http://localhost:${process.env.FS_SMOKE_API_PORT ?? 8000}`,
        // 로컬/스모크 백엔드는 IPv4 loopback에 연결한다.
        agent: new Agent({ family: 4 }),
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    restoreMocks: true,
  },
});
