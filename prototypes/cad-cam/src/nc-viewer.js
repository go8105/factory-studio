import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
export class NCViewer {
  constructor(container, onSelect) {
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color("#f1f2f0");
    this.camera = new THREE.PerspectiveCamera(38, 1, 0.01, 10000000);
    this.camera.up.set(0, 0, 1);
    this.renderer = new THREE.WebGLRenderer({
      antialias: true,
      preserveDrawingBuffer: true,
    });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    container.appendChild(this.renderer.domElement);
    this.renderer.domElement.setAttribute("aria-label", "NC 3D 경로 작업면");
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.paths = new THREE.Group();
    this.scene.add(this.paths);
    this.axes = new THREE.AxesHelper(10);
    this.scene.add(this.axes);
    this.highlight = new THREE.Line(
      new THREE.BufferGeometry(),
      new THREE.LineBasicMaterial({ color: 0x81702f, depthTest: false }),
    );
    this.highlight.renderOrder = 1;
    this.scene.add(this.highlight);
    this.marker = new THREE.Mesh(
      new THREE.SphereGeometry(0.8, 12, 12),
      new THREE.MeshBasicMaterial({ color: 0x81702f }),
    );
    this.marker.visible = false;
    this.scene.add(this.marker);
    new ResizeObserver(() => {
      const w = container.clientWidth,
        h = container.clientHeight;
      if (!w || !h) return;
      this.renderer.setSize(w, h);
      this.camera.aspect = w / h;
      this.camera.updateProjectionMatrix();
    }).observe(container);
    let down;
    this.renderer.domElement.addEventListener("pointerdown", (e) => {
      down = [e.clientX, e.clientY];
    });
    this.renderer.domElement.addEventListener("pointerup", (e) => {
      if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 5)
        return;
      const r = this.renderer.domElement.getBoundingClientRect(),
        ray = new THREE.Raycaster();
      ray.params.Line.threshold = this.pickTolerance ?? 1;
      ray.setFromCamera(
        new THREE.Vector2(
          ((e.clientX - r.left) / r.width) * 2 - 1,
          (-(e.clientY - r.top) / r.height) * 2 + 1,
        ),
        this.camera,
      );
      const hits = ray.intersectObjects(this.paths.children, false);
      if (hits.length) {
        const h = hits[0],
          id = h.object.userData.ids[Math.floor(h.index / 2)];
        onSelect(id);
      }
    });
    this.renderer.setAnimationLoop(() => {
      this.controls.update();
      this.renderer.render(this.scene, this.camera);
    });
    this.fit();
  }
  show(result) {
    for (const child of [...this.paths.children]) {
      child.geometry.dispose();
      child.material.dispose();
      this.paths.remove(child);
    }
    this.result = result;
    this.highlight.visible = false;
    this.marker.visible = false;
    if (result)
      for (const rapid of [true, false]) {
        const positions = [],
          ids = [];
        for (const segment of result.segments)
          if ((segment.code === "G0") === rapid)
            for (let j = 1; j < segment.points.length; j++) {
              positions.push(...segment.points[j - 1], ...segment.points[j]);
              ids.push(segment.id);
            }
        const g = new THREE.BufferGeometry();
        g.setAttribute(
          "position",
          new THREE.Float32BufferAttribute(positions, 3),
        );
        const line = new THREE.LineSegments(
          g,
          new THREE.LineBasicMaterial({ color: rapid ? 0xa28a64 : 0x416977 }),
        );
        line.userData.ids = ids;
        this.paths.add(line);
      }
    this.fit();
  }
  select(id) {
    const s = this.result?.segments[id];
    this.highlight.visible = !!s;
    this.marker.visible = !!s;
    if (!s) return;
    this.highlight.geometry.dispose();
    this.highlight.geometry = new THREE.BufferGeometry().setFromPoints(
      s.points.map((p) => new THREE.Vector3(...p)),
    );
    this.marker.position.set(...s.to);
  }
  fit() {
    const box = new THREE.Box3();
    for (const line of this.paths.children) {
      line.geometry.computeBoundingBox();
      if (line.geometry.attributes.position.count)
        box.union(line.geometry.boundingBox);
    }
    if (box.isEmpty())
      box.set(new THREE.Vector3(-20, -20, -5), new THREE.Vector3(20, 20, 20));
    const center = box.getCenter(new THREE.Vector3()),
      span = Math.max(...box.getSize(new THREE.Vector3()).toArray(), 1);
    this.pickTolerance = span * 0.012;
    this.marker.scale.setScalar(span * 0.008);
    this.axes.scale.setScalar(span / 70);
    this.axes.position.copy(box.min);
    this.controls.target.copy(center);
    this.camera.position
      .copy(center)
      .add(new THREE.Vector3(span * 0.9, -span * 1.2, span * 1));
    this.camera.near = Math.max(0.001, span / 10000);
    this.camera.far = Math.max(1000, span * 20);
    this.camera.updateProjectionMatrix();
    this.controls.update();
  }
}
