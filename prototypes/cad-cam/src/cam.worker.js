import Module from "manifold-3d";
import wasmUrl from "manifold-3d/manifold.wasm?url";
import { generateKernelPaths } from "./cam.js";
let kernel;
self.onmessage = async ({ data }) => {
  try {
    kernel ??= Module({ locateFile: () => wasmUrl }).then((m) => {
      m.setup();
      return m;
    });
    const m = await kernel;
    self.postMessage({
      revision: data.revision,
      path: generateKernelPaths(data.model, data.tool, m.CrossSection),
    });
  } catch (error) {
    kernel = undefined;
    self.postMessage({ revision: data.revision, error: error.message });
  }
};
