import { scenarios, type Scenario } from "./scenarios";
import { useMemo, useRef } from "react";
import { useGLTF } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { Mesh, MeshStandardMaterial } from "three";
import { visionAt, type VisionSnapshot } from "./vision";
export default function VisionCell({
  scenario,
  animated,
  fault,
  onSnapshot,
}: {
  scenario: Scenario;
  animated: boolean;
  fault: boolean;
  onSnapshot: (value: VisionSnapshot) => void;
}) {
  const { scene } = useGLTF("/models/vision-cell.glb");
  const model = useMemo(() => {
    const copy = scene.clone(true);
    copy.traverse((object) => {
      if (object instanceof Mesh) {
        object.castShadow = true;
        object.receiveShadow = true;
        if (object.material instanceof MeshStandardMaterial)
          object.material = object.material.clone();
      }
    });
    return copy;
  }, [scene]);
  const product = useRef<Mesh>(null);
  const elapsed = useRef(0);
  const last = useRef("");
  useFrame((_, dt) => {
    if (animated && !fault) elapsed.current += Math.min(dt, 0.05);
    const value = visionAt(
      elapsed.current,
      fault,
      scenarios[scenario].rejectEvery,
    );
    if (product.current) product.current.position.x = value.x;
    for (const [name, enabled] of [
      ["Inspection_ring", value.scanning && animated],
      ["Lamp_red", fault],
      ["Lamp_amber", !fault && (!animated || scenario === "reject-rise")],
      ["Lamp_green", !fault && animated && scenario !== "reject-rise"],
    ] as const) {
      const mesh = model.getObjectByName(name) as Mesh | undefined;
      if (mesh?.material instanceof MeshStandardMaterial)
        mesh.material.emissiveIntensity = enabled ? 2.5 : 0.03;
    }
    const key = `${value.phase}/${value.result}/${value.inspected}`;
    if (last.current !== key) {
      last.current = key;
      onSnapshot(value);
    }
  });
  return (
    <group>
      <primitive object={model} />
      <mesh ref={product} position={[-1.25, 1.52, 0]} castShadow>
        <boxGeometry args={[0.4, 0.17, 0.38]} />
        <meshStandardMaterial color="#507a65" metalness={0.2} roughness={0.5} />
      </mesh>
    </group>
  );
}
