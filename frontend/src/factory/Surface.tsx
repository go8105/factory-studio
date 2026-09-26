import { useEffect, useMemo } from "react";
import { useThree } from "@react-three/fiber";
import {
  DataTexture,
  RepeatWrapping,
  SRGBColorSpace,
  PMREMGenerator,
} from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
export function FactoryEnvironment() {
  const { gl, scene } = useThree();
  useEffect(() => {
    const generator = new PMREMGenerator(gl);
    const room = new RoomEnvironment();
    const target = generator.fromScene(room, 0, 0.1, 100, { size: 64 });
    const previous = scene.environment;
    scene.environment = target.texture;
    scene.environmentIntensity = 0.45;
    return () => {
      scene.environment = previous;
      target.dispose();
      generator.dispose();
      room.dispose();
    };
  }, [gl, scene]);
  return null;
}
export function FactoryFloor() {
  const texture = useMemo(() => {
    const size = 128;
    const data = new Uint8Array(size * size * 4);
    let seed = 12345;
    for (let y = 0; y < size; y++)
      for (let x = 0; x < size; x++) {
        seed = (seed * 1664525 + 1013904223) >>> 0;
        const grain = (seed % 9) - 4;
        const seam = x === 0 || y === 0 ? 15 : 0;
        const i = (y * size + x) * 4;
        data[i] = 157 + grain - seam;
        data[i + 1] = 171 + grain - seam;
        data[i + 2] = 164 + grain - seam;
        data[i + 3] = 255;
      }
    const map = new DataTexture(data, size, size);
    map.wrapS = map.wrapT = RepeatWrapping;
    map.repeat.set(8, 5);
    map.colorSpace = SRGBColorSpace;
    map.needsUpdate = true;
    return map;
  }, []);
  useEffect(() => () => texture.dispose(), [texture]);
  return (
    <mesh
      rotation={[-Math.PI / 2, 0, 0]}
      position={[0, 0.012, 0]}
      receiveShadow
    >
      <planeGeometry args={[23, 14]} />
      <meshStandardMaterial map={texture} roughness={0.57} metalness={0.06} />
    </mesh>
  );
}
