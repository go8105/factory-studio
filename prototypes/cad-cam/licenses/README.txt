Form Studio E2 CAD kernel notice
Replicad 1.1.0 — MIT (see replicad-MIT.txt)
Replicad OpenCascade.js 1.1.0 — LGPL-2.1-only (see replicad-opencascadejs-LGPL-2.1.txt)
Upstream source and build instructions (version pinned in package-lock.json):
https://github.com/sgenoud/replicad/tree/main/packages/replicad
https://github.com/sgenoud/replicad/tree/main/packages/replicad-opencascadejs
https://github.com/Open-Cascade-SAS/OCCT
https://dev.opencascade.org/resources/licensing
This application does not modify the kernel. JavaScript wrapper and WebAssembly
are separate assets. Replace the dependency with a compatible build, then run
npm install and npm run build in frontend. Source application integration is in
prototypes/cad-cam/src/part-kernel.js and part.worker.js. Preserve these notices
when redistributing. Upstream OCCT additional exception is described at the
Open Cascade licensing URL above; see the packaged license for exact terms.
