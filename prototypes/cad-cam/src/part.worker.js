import { directReferences } from "./part-references.js";
import OC from "replicad-opencascadejs";
import wasmUrl from "replicad-opencascadejs/wasm?url";
import { setKernel, buildPart } from "./part-kernel.js";
let initialization, current;
self.onmessage = async ({ data }) => {
  try {
    initialization ??= OC({ locateFile: () => wasmUrl }).then((oc) => {
      setKernel(oc);
    });
    await initialization;
    if (data.action === "export") {
      if (!current || current.revision !== data.shapeRevision)
        throw Error("먼저 현재 설계를 적용하세요.");
      const blob =
        data.format === "step"
          ? current.shape.blobSTEP()
          : current.shape.blobSTL({
              binary: true,
              tolerance: 0.05,
              angularTolerance: 0.2,
            });
      const bytes = new Uint8Array(await blob.arrayBuffer());
      self.postMessage(
        { revision: data.revision, export: data.format, bytes },
        [bytes.buffer],
      );
      return;
    }
    const start = performance.now(),
      result = buildPart(data.model);
    let mesh, references;
    try {
      mesh = result.shape.mesh({ tolerance: 0.05, angularTolerance: 0.2 });
      references = directReferences(result.shape);
    } catch (error) {
      result.shape.delete();
      throw error;
    }
    if (mesh.vertices.length > 1500000) {
      result.shape.delete();
      throw Error("표시 메시가 너무 큽니다. 피처 개수를 줄이세요.");
    }
    current?.shape.delete();
    current = { shape: result.shape, revision: data.revision };
    self.postMessage({
      revision: data.revision,
      mesh,
      references,
      info: result.info,
      steps: result.steps,
      milliseconds: performance.now() - start,
    });
  } catch (error) {
    self.postMessage({
      revision: data.revision,
      error: error.message ?? String(error),
      featureId: error.featureId,
      featureName: error.featureName,
      steps: error.steps,
    });
  }
};
