import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { STLExporter } from "three/addons/exporters/STLExporter.js";
import { layers, polygonDifference } from "./model.js";

function geometry(positions) {
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
  g.computeVertexNormals();
  return g;
}
function cap(out, polys, z, up) {
  for (const p of polys) {
    const rings = p.map((r) =>
      r.slice(0, -1).map((v) => new THREE.Vector2(...v)),
    );
    const flat = rings.flat();
    for (const face of THREE.ShapeUtils.triangulateShape(
      rings[0],
      rings.slice(1),
    )) {
      const [a, b, c] = face.map((i) => flat[i]);
      const cross = (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x);
      const verts = cross > 0 === up ? [a, b, c] : [a, c, b];
      for (const v of verts) out.push(v.x, v.y, z);
    }
  }
}
export function solidGeometry(model) {
  const ls = layers(model),
    out = [];
  if (!ls.length) return geometry(out);
  cap(out, ls[0].polygons, 0, false);
  for (let i = 0; i < ls.length; i++) {
    const { z0, z1, polygons } = ls[i];
    for (const p of polygons)
      for (const r of p)
        for (let j = 0; j < r.length - 1; j++) {
          const [x, y] = r[j],
            [u, v] = r[j + 1];
          out.push(x, y, z0, u, v, z0, u, v, z1, x, y, z0, u, v, z1, x, y, z1);
        }
    cap(out, polygonDifference(polygons, ls[i + 1]?.polygons ?? []), z1, true);
  }
  return geometry(out);
}
export function gridGeometry(grid) {
  const out = [],
    { nx, ny, dx, dy, minX, minY, heights } = grid;
  const quad = (a, b, c, d) => out.push(...a, ...b, ...c, ...a, ...c, ...d);
  for (let y = 0; y < ny; y++)
    for (let x = 0; x < nx; x++) {
      const z = heights[y * nx + x];
      if (z <= 0) continue;
      const x0 = minX + x * dx,
        x1 = x0 + dx,
        y0 = minY + y * dy,
        y1 = y0 + dy;
      quad([x0, y0, z], [x1, y0, z], [x1, y1, z], [x0, y1, z]);
      const left = x ? heights[y * nx + x - 1] : 0,
        right = x < nx - 1 ? heights[y * nx + x + 1] : 0;
      const down = y ? heights[(y - 1) * nx + x] : 0,
        up = y < ny - 1 ? heights[(y + 1) * nx + x] : 0;
      if (z > down)
        quad([x0, y0, down], [x1, y0, down], [x1, y0, z], [x0, y0, z]);
      if (z > right)
        quad([x1, y0, right], [x1, y1, right], [x1, y1, z], [x1, y0, z]);
      if (z > up) quad([x1, y1, up], [x0, y1, up], [x0, y1, z], [x1, y1, z]);
      if (z > left)
        quad([x0, y1, left], [x0, y0, left], [x0, y0, z], [x0, y1, z]);
    }
  return geometry(out);
}
export class Viewer {
  constructor(container, onSelect) {
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color("#f1f2f0");
    this.camera = new THREE.PerspectiveCamera(35, 1, 0.1, 5000);
    this.camera.up.set(0, 0, 1);
    this.renderer = new THREE.WebGLRenderer({
      antialias: true,
      preserveDrawingBuffer: true,
    });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    container.appendChild(this.renderer.domElement);
    this.renderer.domElement.setAttribute("aria-label", "3D 부품 작업면");
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.minDistance = 8;
    this.controls.maxDistance = 1500;
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x85909c, 2.6));
    const key = new THREE.DirectionalLight(0xffffff, 3);
    key.position.set(80, -100, 180);
    this.scene.add(key);
    const fill = new THREE.DirectionalLight(0xe0e9f2, 1.8);
    fill.position.set(-100, 80, 40);
    this.scene.add(fill);
    const grid = new THREE.GridHelper(500, 50, 0xc1c7c9, 0xe0e4e2);
    grid.rotation.x = Math.PI / 2;
    grid.position.z = -0.05;
    this.scene.add(grid);
    this.grid = grid;
    const axes = new THREE.AxesHelper(22);
    axes.position.set(-65, -55, 0.1);
    this.scene.add(axes);
    this.axes = axes;
    this.material = new THREE.MeshStandardMaterial({
      color: 0x92a8ad,
      roughness: 0.44,
      metalness: 0.16,
      side: THREE.DoubleSide,
    });
    this.simMaterial = new THREE.MeshStandardMaterial({
      color: 0xbbac8e,
      roughness: 0.65,
      metalness: 0.12,
      side: THREE.DoubleSide,
    });
    this.part = new THREE.Mesh(new THREE.BufferGeometry(), this.material);
    this.scene.add(this.part);
    this.paths = new THREE.Group();
    this.scene.add(this.paths);
    this.tool = new THREE.Group();
    this.scene.add(this.tool);
    this.tool.visible = false;
    this.toolBit = new THREE.Mesh(
      new THREE.CylinderGeometry(1, 1, 14, 32),
      new THREE.MeshStandardMaterial({
        color: 0x536a78,
        metalness: 0.7,
        roughness: 0.25,
      }),
    );
    this.toolBit.rotation.x = Math.PI / 2;
    this.toolBit.position.z = 7;
    this.tool.add(this.toolBit);
    const holder = new THREE.Mesh(
      new THREE.CylinderGeometry(5, 4, 16, 24),
      new THREE.MeshStandardMaterial({
        color: 0x27333e,
        metalness: 0.45,
        roughness: 0.35,
      }),
    );
    holder.rotation.x = Math.PI / 2;
    holder.position.z = 22;
    this.tool.add(holder);
    this.fit(null);
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
      ray.setFromCamera(
        new THREE.Vector2(
          ((e.clientX - r.left) / r.width) * 2 - 1,
          (-(e.clientY - r.top) / r.height) * 2 + 1,
        ),
        this.camera,
      );
      const hit = ray.intersectObject(this.part)[0];
      if (hit) onSelect(hit.point);
    });
    this.renderer.setAnimationLoop(() => {
      this.controls.update();
      this.renderer.render(this.scene, this.camera);
    });
  }
  fit(stock) {
    const x = stock?.x ?? 0,
      y = stock?.y ?? 0,
      z = (stock?.height ?? 10) / 3,
      size =
        Math.max(stock?.w ?? 100, stock?.h ?? 80, stock?.height ?? 0) * 1.8;
    this.controls.target.set(x, y, z);
    this.camera.position.set(x + size * 0.8, y - size, z + size * 0.9);
    this.controls.update();
    this.axes.position.set(
      x - (stock?.w ?? 90) / 2 - 15,
      y - (stock?.h ?? 70) / 2 - 15,
      0,
    );
  }
  top(stock) {
    const x = stock?.x ?? 0,
      y = stock?.y ?? 0;
    this.controls.target.set(x, y, 0);
    this.camera.position.set(
      x,
      y - 0.001,
      Math.max(stock?.w ?? 100, stock?.h ?? 80) * 2.5,
    );
    this.controls.update();
  }
  setGeometry(g, sim = false) {
    this.part.geometry.dispose();
    this.part.geometry = g;
    this.part.material = sim ? this.simMaterial : this.material;
  }
  showModel(model) {
    this.setGeometry(solidGeometry(model));
    this.tool.visible = false;
    this.paths.visible = false;
  }
  showSimulation(grid, pos, diameter) {
    this.setGeometry(gridGeometry(grid), true);
    this.tool.visible = true;
    this.toolBit.scale.set(diameter / 2, 1, diameter / 2);
    if (pos) this.tool.position.set(pos.x, pos.y, pos.z);
  }
  setPaths(path) {
    for (const child of [...this.paths.children]) {
      child.geometry.dispose();
      child.material.dispose();
      this.paths.remove(child);
    }
    if (!path) return;
    for (const cut of [true, false]) {
      const pts = [];
      for (let i = 1; i < path.points.length; i++) {
        const a = path.points[i - 1],
          b = path.points[i];
        if (b.cut === cut) pts.push(a.x, a.y, a.z + 0.04, b.x, b.y, b.z + 0.04);
      }
      const g = new THREE.BufferGeometry();
      g.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
      this.paths.add(
        new THREE.LineSegments(
          g,
          new THREE.LineBasicMaterial({
            color: cut ? 0x397e89 : 0xb78c53,
            transparent: true,
            opacity: cut ? 0.7 : 0.38,
          }),
        ),
      );
    }
    this.paths.visible = true;
  }
  stl(model) {
    const mesh = new THREE.Mesh(solidGeometry(model));
    const data = new STLExporter().parse(mesh, { binary: true });
    mesh.geometry.dispose();
    return data;
  }
}
