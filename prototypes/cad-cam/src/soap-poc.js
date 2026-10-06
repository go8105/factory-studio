import "./soap-poc.css";
import * as T from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { STLLoader } from "three/addons/loaders/STLLoader.js";
const base = import.meta.env.BASE_URL,
  el = document.querySelector("#viewport"),
  status = document.querySelector("#status");
const scene = new T.Scene();
scene.background = new T.Color("#eceeec");
const camera = new T.PerspectiveCamera(40, 1, 0.1, 1500);
camera.up.set(0, 0, 1);
camera.position.set(300, -470, 350);
const renderer = new T.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
el.append(renderer.domElement);
const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0, -45, 55);
controls.enableDamping = true;
scene.add(new T.HemisphereLight(0xffffff, 0x687581, 2.7));
const light = new T.DirectionalLight(0xffffff, 3);
light.position.set(-40, -90, 180);
scene.add(light);
const grid = new T.GridHelper(260, 26, 0xb8c0c0, 0xd4d9d7);
grid.rotation.x = Math.PI / 2;
grid.position.z = -1.5;
scene.add(grid);
function mesh(geo, color, soft = false) {
  geo.computeVertexNormals();
  return new T.Mesh(
    geo,
    new T.MeshStandardMaterial({
      color,
      roughness: soft ? 0.9 : 0.6,
      flatShading: !soft,
    }),
  );
}
const sample = mesh(new T.BoxGeometry(50, 40, 18), 0x99c8d4);
sample.visible = false;
scene.add(sample);
try {
  const loader = new STLLoader(),
    names = [
      "base-v3",
      "carrier-v3",
      "lid-v3",
      "plate-v3",
      "drawer-v3",
      "hinge-pin-v3",
      "sleeve-v3",
      "cover-v3",
      "boot-v3",
    ];
  const geometry = await Promise.all(
    names.map((n) => loader.loadAsync(base + "soap-poc/" + n + ".stl")),
  );
  const [body, carrier, lid, plate, drawer, pin, sleeve, cover, boot] =
    geometry.map((g, i) =>
      mesh(
        g,
        [
          0x9ba7af, 0x788892, 0xa4b0b5, 0x314d60, 0x91a1aa, 0x4e626e, 0x7e9f9c,
          0x7e9f9c, 0x7e9f9c,
        ][i],
        i >= 6,
      ),
    );
  scene.add(body, plate, drawer, sleeve, boot);
  boot.position.z = -1.2;
  plate.position.z = 15;
  drawer.position.z = 1.8;
  sleeve.position.z = 15.5;
  const upper = new T.Group();
  scene.add(upper);
  upper.add(carrier, pin);
  carrier.position.z = 33;
  pin.rotation.y = Math.PI / 2;
  pin.position.set(-30, 56, 39);
  const hinge = new T.Group();
  hinge.position.set(0, 56, 39);
  upper.add(hinge);
  hinge.add(lid, cover);
  lid.rotation.x = Math.PI;
  lid.position.set(0, -56, 4);
  cover.rotation.x = Math.PI;
  cover.position.set(0, -56, 5.4);
  const rest = Float32Array.from(sleeve.geometry.attributes.position.array);
  function update() {
    const open = +document.querySelector("#lid").value,
      twist = +document.querySelector("#rotor").value,
      press = +document.querySelector("#press").value,
      travel = +document.querySelector("#drawer").value;
    hinge.rotation.x = -T.MathUtils.degToRad(open);
    upper.rotation.z = T.MathUtils.degToRad(twist);
    upper.position.z = -press;
    drawer.position.y = -travel;
    // Display-only deformation, with no material/stress/force solver.
    const pos = sleeve.geometry.attributes.position;
    for (let i = 0; i < pos.count; i++) {
      const x = rest[i * 3],
        y = rest[i * 3 + 1],
        z = rest[i * 3 + 2],
        t = Math.max(0, Math.min(1, z / 17.5)),
        a = T.MathUtils.degToRad(twist) * t;
      pos.setXYZ(
        i,
        x * Math.cos(a) - y * Math.sin(a),
        x * Math.sin(a) + y * Math.cos(a),
        (z * (17.5 - press)) / 17.5,
      );
    }
    pos.needsUpdate = true;
    sleeve.geometry.computeVertexNormals();
    sleeve.geometry.computeBoundingSphere();
    sample.visible = document.querySelector("#soap").checked;
    sample.scale.z = (18 - press) / 18;
    sample.position.z = 19 + (18 - press) / 2;
    sample.rotation.z = T.MathUtils.degToRad(twist);
    sleeve.material.transparent =
      document.querySelector("#transparent").checked;
    sleeve.material.opacity = sleeve.material.transparent ? 0.2 : 1;
    sleeve.material.depthWrite = !sleeve.material.transparent;
    for (const [id, value] of [
      ["lid", open + "°"],
      ["rotor", twist + "°"],
      ["press", press + " mm"],
      ["drawer", travel + " mm"],
    ])
      document.querySelector("#" + id + "Value").textContent = value;
    document.querySelector("#assemblyState").textContent =
      travel === 115
        ? "가루통 완전 분리 · 외피 변형과 독립"
        : press > 0
          ? `누름 ${press} mm · 비누 두께 ${18 - press} mm 가정 · 탄성 해석 아님`
          : open === 0
            ? "닫힌 상태 · 위 케이스를 누르고 조금 비틀기"
            : "열린 상태 · 비누 교체/내부 확인";
    document.querySelector("#partDownload").href =
      base + "soap-poc/" + document.querySelector("#part").value + ".stl";
  }
  ["lid", "rotor", "press", "drawer", "soap", "transparent", "part"].forEach(
    (id) =>
      document.getElementById(id).addEventListener("input", () => {
        if (id === "lid" && +document.querySelector("#lid").value > 0) {
          document.querySelector("#press").value = 0;
          document.querySelector("#rotor").value = 0;
        }
        if (id === "press" || id === "rotor")
          document.querySelector("#lid").value = 0;
        update();
      }),
  );
  document.querySelector("#remove").addEventListener("click", () => {
    document.querySelector("#drawer").value = 115;
    update();
  });
  update();
  document.querySelector("#remove").disabled = false;
  status.textContent =
    "부품 9개 로드 완료 · 단단한 부품 간섭 검사 통과 · 탄성/실물 미검증";
} catch (error) {
  status.textContent =
    "설계 파일 접근 실패 · 관리자 세션과 서버 빌드를 확인하세요.";
  console.error(error);
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

const researchLink = document.querySelector("#researchLink");
researchLink.href = `${base}research-notebook.html?scope=${encodeURIComponent(new URLSearchParams(location.search).get("scope") || "local")}`;
