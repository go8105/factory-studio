import OC from "replicad-opencascadejs";
import wasmUrl from "replicad-opencascadejs/wasm?url";
import { setOC } from "replicad";
import { readReference } from "./nc-step.js";
self.onmessage = async ({ data }) => {
  try {
    setOC(await OC({ locateFile: () => wasmUrl }));
    const reference = await readReference(data.file);
    const hash = await crypto.subtle.digest(
      "SHA-256",
      await data.file.arrayBuffer(),
    );
    reference.sourceHash = Array.from(new Uint8Array(hash), (v) =>
      v.toString(16).padStart(2, "0"),
    ).join("");
    reference.fileName = data.file.name;
    self.postMessage({ revision: data.revision, reference });
  } catch (error) {
    self.postMessage({ revision: data.revision, error: error.message });
  }
};
