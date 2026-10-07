import Module from "manifold-3d";
import wasmUrl from "manifold-3d/manifold.wasm?url";
import { generateKernelPaths, generatePathProposals } from "./cam.js";
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
      ...(data.action === "propose"
        ? {
            proposals: generatePathProposals(
              data.model,
              data.tool,
              m.CrossSection,
            ),
          }
        : { path: generateKernelPaths(data.model, data.tool, m.CrossSection) }),
    });
  } catch (error) {
    kernel = undefined;
    self.postMessage({ revision: data.revision, error: error.message });
  }
};
