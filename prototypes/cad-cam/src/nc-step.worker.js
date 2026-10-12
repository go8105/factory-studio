import OC from "replicad-opencascadejs";
import wasmUrl from "replicad-opencascadejs/wasm?url";
import { setOC } from "replicad";
import { readReference } from "./nc-step.js";
self.onmessage = async ({ data }) => {
  try {
    self.postMessage({
      revision: data.revision,
      progress:
        "STEP 3D 커널 다운로드 중… 첫 실행은 네트워크에 따라 시간이 걸립니다.",
      phase: "prepare",
    });
    const response = await fetch(wasmUrl);
    if (!response.ok)
      throw Error(`3D 커널 다운로드 실패 HTTP ${response.status}`);
    const binary = await response.arrayBuffer();
    self.postMessage({
      revision: data.revision,
      progress: "STEP 3D 커널 초기화 중…",
      phase: "prepare",
    });
    setOC(await OC({ wasmBinary: binary, locateFile: () => wasmUrl }));
    self.postMessage({
      revision: data.revision,
      progress: "STEP 형상 읽는 중…",
      phase: "read",
    });
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
