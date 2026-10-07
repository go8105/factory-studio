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
        find: /^replicad-opencascadejs\/wasm(?=\?|$)/,
        replacement: require.resolve("replicad-opencascadejs/wasm"),
      },
      {
        find: /^replicad-opencascadejs$/,
        replacement: require
          .resolve("replicad-opencascadejs")
          .replace(".cjs", ".js"),
      },
      {
        find: /^replicad$/,
        replacement: require
          .resolve("replicad")
          .replace("replicad.umd.cjs", "replicad.js"),
      },
      {
        find: /^manifold-3d\/manifold\.wasm(?=\?|$)/,
        replacement: require.resolve("manifold-3d/manifold.wasm"),
      },
      {
        find: /^manifold-3d$/,
        replacement: require.resolve("manifold-3d/manifold.js"),
      },
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
    rollupOptions: {
      input: {
        editor: path("../../prototypes/cad-cam/index.html"),
        part: path("../../prototypes/cad-cam/part-design.html"),
        nc: path("../../prototypes/cad-cam/nc-review.html"),
      },
    },
  },
});
await cp(
  path("../../prototypes/cad-cam/licenses"),
  path("../public/cad-cam-app/licenses"),
  { recursive: true },
);
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
