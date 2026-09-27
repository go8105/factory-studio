import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { RoundedBox } from "@react-three/drei";
import type { Group } from "three";
type Vec = [number, number, number];
function Part({
  at,
  size,
  color,
  radius = 0.035,
}: {
  at: Vec;
  size: Vec;
  color: string;
  radius?: number;
}) {
  return (
    <RoundedBox
      position={at}
      args={size}
      radius={radius}
      smoothness={2}
      castShadow
      receiveShadow
    >
      <meshStandardMaterial color={color} roughness={0.72} />
    </RoundedBox>
  );
}
function Oval({ at, size, color }: { at: Vec; size: Vec; color: string }) {
  return (
    <mesh position={at} scale={size} castShadow>
      <sphereGeometry args={[1, 20, 14]} />
      <meshStandardMaterial color={color} roughness={0.78} />
    </mesh>
  );
}
function Technician({ animated }: { animated: boolean }) {
  const head = useRef<Group>(null);
  const time = useRef(0);
  useFrame((_, dt) => {
    if (animated) time.current += Math.min(dt, 0.05);
    if (head.current)
      head.current.rotation.y = Math.sin(time.current * 0.45) * 0.1;
  });
  return (
    <group position={[2.35, 0, 2.15]} rotation={[0, 0.55, 0]}>
      {[-0.105, 0.105].map((x) => (
        <group key={x}>
          <Part
            at={[x, 0.09, 0.055]}
            size={[0.17, 0.17, 0.31]}
            color="#252a2d"
          />
          <Part
            at={[x, 0.035, 0.055]}
            size={[0.18, 0.045, 0.32]}
            color="#13191d"
            radius={0.018}
          />
          <Part at={[x, 0.48, 0]} size={[0.175, 0.71, 0.2]} color="#354657" />
          <Part
            at={[x, 0.54, 0.103]}
            size={[0.145, 0.028, 0.016]}
            color="#465666"
            radius={0.006}
          />
        </group>
      ))}
      <Part at={[0, 0.94, 0]} size={[0.39, 0.25, 0.24]} color="#354657" />
      <Part
        at={[0, 1.19, 0]}
        size={[0.44, 0.48, 0.26]}
        color="#bbc2c0"
        radius={0.065}
      />
      <Part
        at={[0, 1.18, 0.139]}
        size={[0.025, 0.42, 0.018]}
        color="#45535b"
        radius={0.006}
      />
      {[-0.12, 0.12].map((x) => (
        <group key={x}>
          <Part
            at={[x, 1.12, 0.145]}
            size={[0.14, 0.12, 0.025]}
            color="#a4aeae"
            radius={0.008}
          />
          <Part
            at={[x, 1.32, 0.14]}
            size={[0.16, 0.026, 0.018]}
            color="#e4e5d9"
            radius={0.005}
          />
          <group
            position={[x < 0 ? -0.26 : 0.26, 1.32, 0]}
            rotation={[-0.3, 0, x < 0 ? 0.1 : -0.1]}
          >
            <Part
              at={[0, -0.14, 0]}
              size={[0.16, 0.33, 0.18]}
              color="#354657"
            />
            <group
              position={[0, -0.28, 0]}
              rotation={[-1.1, 0, x < 0 ? 0.3 : -0.3]}
            >
              <Part
                at={[0, -0.11, 0]}
                size={[0.13, 0.25, 0.15]}
                color="#354657"
              />
              <Oval
                at={[0, -0.25, 0]}
                size={[0.065, 0.09, 0.043]}
                color="#c4a58d"
              />
            </group>
          </group>
        </group>
      ))}
      <group position={[0, 1.07, 0.34]} rotation={[-0.75, 0, 0]}>
        <Part
          at={[0, 0, 0]}
          size={[0.34, 0.24, 0.026]}
          color="#28343e"
          radius={0.012}
        />
        <Part
          at={[0, 0, 0.016]}
          size={[0.3, 0.2, 0.006]}
          color="#68888c"
          radius={0.002}
        />
      </group>
      <Oval at={[0, 1.47, 0]} size={[0.072, 0.09, 0.07]} color="#c4a58d" />
      <group ref={head} position={[0, 1.61, 0]}>
        <Oval at={[0, 0, 0]} size={[0.13, 0.175, 0.12]} color="#c4a58d" />
        <Oval
          at={[0, 0.025, 0.12]}
          size={[0.027, 0.04, 0.034]}
          color="#b79780"
        />
        {[-0.053, 0.053].map((x) => (
          <Oval
            key={x}
            at={[x, 0.05, 0.106]}
            size={[0.018, 0.008, 0.009]}
            color="#3a3734"
          />
        ))}
        <Oval
          at={[0, -0.067, 0.109]}
          size={[0.035, 0.006, 0.006]}
          color="#8d6d60"
        />
        {[-0.13, 0.13].map((x) => (
          <Oval
            key={x}
            at={[x, 0, 0]}
            size={[0.025, 0.05, 0.025]}
            color="#c4a58d"
          />
        ))}
        <Oval
          at={[0, 0.13, -0.007]}
          size={[0.15, 0.085, 0.145]}
          color="#ece9de"
        />
        <Part
          at={[0, 0.1, 0.045]}
          size={[0.33, 0.025, 0.32]}
          color="#e2e0d5"
          radius={0.01}
        />
      </group>
    </group>
  );
}
export default function InspectionZone({ animated }: { animated: boolean }) {
  return (
    <group>
      <Technician animated={animated} />
      {/* Local ceiling services and task lighting around the inspection cell. */}
      {[2.3, 5.7].map((x) => (
        <group key={x}>
          <Part at={[x, 4.5, 0]} size={[0.09, 0.12, 5]} color="#7b8589" />
          <Part at={[x, 4.36, 0.4]} size={[0.23, 0.075, 2.2]} color="#e5e8e5" />
          <mesh position={[x, 4.31, 0.4]} rotation={[-Math.PI / 2, 0, 0]}>
            <planeGeometry args={[0.18, 2.1]} />
            <meshStandardMaterial
              color="#fff4dd"
              emissive="#fff4dd"
              emissiveIntensity={2}
            />
          </mesh>
          <pointLight
            position={[x, 3.9, 0.4]}
            intensity={7}
            distance={7}
            color="#fff2dc"
          />
        </group>
      ))}
      {[-1.9, 3].map((z) => (
        <Part
          key={z}
          at={[4, 0.026, z]}
          size={[3.8, 0.018, 0.045]}
          color="#bd9f54"
          radius={0.002}
        />
      ))}
      <Part
        at={[6, 0.026, 0.55]}
        size={[0.045, 0.018, 4.9]}
        color="#bd9f54"
        radius={0.002}
      />
      <Part
        at={[3.9, 0.035, 2.25]}
        size={[1.45, 0.024, 0.75]}
        color="#586365"
        radius={0.006}
      />
      {Array.from({ length: 13 }, (_, i) => (
        <Part
          key={i}
          at={[3.27 + i * 0.1, 0.05, 2.25]}
          size={[0.012, 0.006, 0.65]}
          color="#74807f"
          radius={0.002}
        />
      ))}
    </group>
  );
}
