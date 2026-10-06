import { build } from "vite";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import { cp, mkdir } from "node:fs/promises";
const require = createRequire(new URL("../package.json", import.meta.url));
const path = (p) => fileURLToPath(new URL(p, import.meta.url));
const shared = {
  configFile: false,
  root: path("../../prototypes/cad-cam"),
  publicDir: false,
  resolve: {
    alias: [
      {
        find: /^three$/,
        replacement: require
          .resolve("three")
          .replace("three.cjs", "three.module.js"),
      },
      {
        find: "three/addons",
        replacement: path("../node_modules/three/examples/jsm"),
      },
      {
        find: "polygon-clipping",
        replacement: require.resolve("polygon-clipping"),
      },
    ],
  },
};
await build({
  ...shared,
  base: "/cad-cam-app/",
  build: {
    outDir: path("../public/cad-cam-app"),
    emptyOutDir: true,
    rollupOptions: { input: path("../../prototypes/cad-cam/index.html") },
  },
});
const privateRoot = path("../../backend/private-assets/soap-poc");
await build({
  ...shared,
  base: "/api/v1/cad/admin/soap-poc/",
  build: {
    outDir: privateRoot,
    emptyOutDir: true,
    rollupOptions: {
      input: {
        soap: path("../../prototypes/cad-cam/soap-poc.html"),
        research: path("../../prototypes/cad-cam/research-notebook.html"),
      },
    },
  },
});
await mkdir(privateRoot + "/soap-poc", { recursive: true });
await cp(
  path("../../prototypes/cad-cam/private/soap-poc"),
  privateRoot + "/soap-poc",
  { recursive: true },
);
await import("./verify-cad-assets.mjs");
