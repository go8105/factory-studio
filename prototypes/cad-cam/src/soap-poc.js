import "./soap-poc.css";
import * as T from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { STLLoader } from "three/addons/loaders/STLLoader.js";
const base = import.meta.env.BASE_URL;
const scope = new URLSearchParams(location.search).get("scope");
if (scope)
  document.querySelector("header a").href =
    `./index.html?scope=${encodeURIComponent(scope)}`;
if (new URLSearchParams(location.search).get("embedded") === "1") {
  const link = document.querySelector("header a");
  link.href = "/cad-cam";
  link.target = "_parent";
}
const el = document.querySelector("#viewport"),
  status = document.querySelector("#status");
const scene = new T.Scene();
scene.background = new T.Color("#eceeec");
const camera = new T.PerspectiveCamera(38, 1, 0.1, 1000);
camera.up.set(0, 0, 1);
camera.position.set(115, -140, 125);
const renderer = new T.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
el.append(renderer.domElement);
const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0, 0, 12);
controls.enableDamping = true;
scene.add(new T.HemisphereLight(0xffffff, 0x737c85, 2.7));
const light = new T.DirectionalLight(0xffffff, 3);
light.position.set(-40, -80, 150);
scene.add(light);
const grid = new T.GridHelper(180, 18, 0xb8c0c0, 0xd4d9d7);
grid.rotation.x = Math.PI / 2;
grid.position.z = -0.2;
scene.add(grid);
const loader = new STLLoader(),
  plates = {};
function mesh(geometry, color) {
  geometry.computeVertexNormals();
  const obj = new T.Mesh(
    geometry,
    new T.MeshStandardMaterial({ color, roughness: 0.65, flatShading: true }),
  );
  scene.add(obj);
  return obj;
}
const sample = mesh(new T.BoxGeometry(20, 18, 8), 0xd4cbb3);
sample.visible = false;
try {
  const parts = await Promise.all(
    ["tray", "plate-A", "plate-B", "plate-C"].map((n) =>
      loader.loadAsync(base + "soap-poc/" + n + ".stl"),
    ),
  );
  mesh(parts[0], 0xabb6ba);
  ["A", "B", "C"].forEach((key, i) => {
    plates[key] = mesh(parts[i + 1], 0x344e62);
  });
  function update() {
    const key = document.querySelector("#variant").value,
      offset = Number(document.querySelector("#explode").value);
    for (const [k, p] of Object.entries(plates)) {
      p.visible = k === key;
      p.position.z = 10 + offset;
    }
    const h = { A: 0.6, B: 1, C: 1.4 }[key];
    sample.position.z = 17 + h + offset;
    sample.visible = document.querySelector("#soap").checked;
    document.querySelector("#distance").textContent = offset + " mm";
    document.querySelector("#partTitle").textContent =
      key + " / 돌기 " + h.toFixed(1) + " mm";
    document.querySelector("#plateDownload").href =
      base + "soap-poc/plate-" + key + ".stl";
  }
  ["variant", "explode", "soap"].forEach((id) =>
    document.getElementById(id).addEventListener("input", update),
  );
  update();
  status.textContent = "부품 4개 로드 완료 · 실물 출력·절삭 성능 미검증";
} catch (error) {
  status.textContent = "형상 로드 실패: " + error.message;
}
new ResizeObserver(() => {
  const { width, height } = el.getBoundingClientRect();
  renderer.setSize(width, height);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}).observe(el);
renderer.setAnimationLoop(() => {
  controls.update();
  renderer.render(scene, camera);
});
