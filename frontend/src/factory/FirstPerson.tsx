import { relativeStep } from "./world";
import { useEffect, useRef, type RefObject } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { PerspectiveCamera, Raycaster, Vector2, type Scene } from "three";
import { inputVector, move, type Direction, type Point } from "./world";

function selectedStation(ray: Raycaster, scene: Scene): number | null {
  // Inspect the nearest visible surface, so walls and equipment block selection.
  ray.far = 7;
  const hit = ray.intersectObjects(scene.children, true).find(({ object }) => {
    for (let item = object; item; item = item.parent!)
      if (!item.visible) return false;
    return true;
  });
  for (let item = hit?.object; item; item = item.parent!) {
    if (typeof item.userData.station === "number") return item.userData.station;
  }
  return null;
}

export default function FirstPerson({
  position,
  keys,
  reset,
  inspect,
  onSelect,
  onTarget,
}: {
  position: RefObject<Point>;
  keys: RefObject<Set<Direction>>;
  reset: number;
  inspect: number;
  onSelect: (i: number) => void;
  onTarget: (i: number | null) => void;
}) {
  const { camera, gl, scene } = useThree();
  useEffect(() => {
    if (!(camera instanceof PerspectiveCamera)) return;
    const previous = camera.fov;
    camera.fov = 62;
    camera.updateProjectionMatrix();
    return () => {
      camera.fov = previous;
      camera.updateProjectionMatrix();
    };
  }, [camera]);
  const angle = useRef({ yaw: 0, pitch: -0.06 });
  const target = useRef<number | null>(null);
  const ray = useRef(new Raycaster());
  useEffect(() => {
    angle.current = { yaw: 0, pitch: -0.06 };
  }, [reset]);
  useEffect(() => {
    if (inspect > 0 && target.current !== null) onSelect(target.current);
  }, [inspect, onSelect]);
  useEffect(() => {
    const canvas = gl.domElement;
    let drag: { id: number; x: number; y: number } | null = null;
    let distance = 0;
    const down = (e: PointerEvent) => {
      if (e.button === 0) {
        distance = 0;
        drag = { id: e.pointerId, x: e.clientX, y: e.clientY };
      }
    };
    const change = (e: PointerEvent) => {
      if (!drag || drag.id !== e.pointerId) return;
      distance += Math.hypot(e.clientX - drag.x, e.clientY - drag.y);
      angle.current.yaw -= (e.clientX - drag.x) * 0.004;
      angle.current.pitch = Math.max(
        -1.1,
        Math.min(1.1, angle.current.pitch - (e.clientY - drag.y) * 0.004),
      );
      drag = { id: e.pointerId, x: e.clientX, y: e.clientY };
    };
    const up = () => {
      drag = null;
    };
    const click = (e: MouseEvent) => {
      if (distance > 5) return;
      const box = canvas.getBoundingClientRect();
      const pick = new Raycaster();
      pick.setFromCamera(
        new Vector2(
          ((e.clientX - box.left) / box.width) * 2 - 1,
          1 - ((e.clientY - box.top) / box.height) * 2,
        ),
        camera,
      );
      const selected = selectedStation(pick, scene);
      if (selected !== null) onSelect(selected);
    };
    canvas.addEventListener("click", click);
    canvas.addEventListener("pointerdown", down);
    window.addEventListener("pointermove", change);
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", up);
    window.addEventListener("blur", up);
    return () => {
      canvas.removeEventListener("click", click);
      canvas.removeEventListener("pointerdown", down);
      window.removeEventListener("pointermove", change);
      window.removeEventListener("pointerup", up);
      window.removeEventListener("pointercancel", up);
      window.removeEventListener("blur", up);
    };
  }, [gl, camera, scene, onSelect]);
  useFrame((_, dt) => {
    const delta = inputVector(keys.current, dt);
    const step = relativeStep(delta.x, delta.z, angle.current.yaw);
    position.current = move(position.current, step.x, step.z);
    const p = position.current;
    camera.position.set(p.x, p.y + 1.68, p.z);
    camera.rotation.set(angle.current.pitch, angle.current.yaw, 0, "YXZ");
    ray.current.setFromCamera(new Vector2(0, 0), camera);
    ray.current.far = 7;
    const next = selectedStation(ray.current, scene);
    if (target.current !== next) {
      target.current = next;
      onTarget(next);
    }
  });
  return null;
}
