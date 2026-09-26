import { useMemo } from "react";
import { useGLTF } from "@react-three/drei";
import { Mesh } from "three";
export default function Building({
  exterior,
  walking,
}: {
  exterior: boolean;
  walking: boolean;
}) {
  const { scene } = useGLTF("/models/factory-building.glb");
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
  // Independent named export groups support a cutaway without remodelling the scene.
  const groups = useMemo(
    () =>
      Object.fromEntries(model.children.map((child) => [child.name, child])),
    [model],
  );
  return (
    <group>
      {Object.entries(groups).map(([name, object]) => (
        <primitive
          key={name}
          object={object}
          visible={
            name === "Roof" || name === "Envelope"
              ? exterior
              : name === "Overhead"
                ? exterior || walking
                : true
          }
        />
      ))}
    </group>
  );
}
