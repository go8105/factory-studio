import { build } from "vite";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
const require = createRequire(new URL("../package.json", import.meta.url));
await build({
  configFile: false,
  root: fileURLToPath(new URL("../../prototypes/cad-cam", import.meta.url)),
  base: "/cad-cam-app/",
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
        replacement: fileURLToPath(
          new URL("../node_modules/three/examples/jsm", import.meta.url),
        ),
      },
      {
        find: "polygon-clipping",
        replacement: require.resolve("polygon-clipping"),
      },
    ],
  },
  build: {
    outDir: fileURLToPath(new URL("../public/cad-cam-app", import.meta.url)),
    emptyOutDir: true,
    rollupOptions: {
      input: {
        main: fileURLToPath(
          new URL("../../prototypes/cad-cam/index.html", import.meta.url),
        ),
        soap: fileURLToPath(
          new URL("../../prototypes/cad-cam/soap-poc.html", import.meta.url),
        ),
      },
    },
  },
});
