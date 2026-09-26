import { useMemo, useRef } from "react";
import { useGLTF } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { Mesh } from "three";
export default function ProductionCell({
  index,
  animated,
}: {
  index: number;
  animated: boolean;
}) {
  const { scene } = useGLTF(
    `/models/${index === 0 ? "assembly" : "packaging"}-cell.glb`,
  );
  const model = useMemo(() => {
    const copy = scene.clone(true);
    copy.traverse((object) => {
      if (object instanceof Mesh) {
        object.castShadow = true;
        object.receiveShadow = true;
      }
    });
    return copy;
  }, [scene]);
  const time = useRef(0);
  const head = useMemo(
    () => model.getObjectByName(index === 0 ? "PressHead" : "Sealer"),
    [model, index],
  );
  useFrame((_, dt) => {
    if (animated) time.current += Math.min(dt, 0.05);
    if (head)
      head.position.y =
        (index === 0 ? 2.05 : 2.08) -
        ((index === 0 ? 0.23 : 0.1) * (1 - Math.cos(time.current * 1.5))) / 2;
  });
  return <primitive object={model} />;
}
