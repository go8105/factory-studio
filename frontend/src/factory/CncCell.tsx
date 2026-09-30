import { useMemo } from "react";
import { CylinderGeometry, Quaternion, Shape, Path, Vector3 } from "three";
import { cncPose, type CncPoint, type CncState } from "./cnc";
function Box({
  at,
  size,
  color = "#cdd6d4",
}: {
  at: CncPoint;
  size: CncPoint;
  color?: string;
}) {
  return (
    <mesh position={at} castShadow receiveShadow>
      <boxGeometry args={size} />
      <meshStandardMaterial color={color} metalness={0.3} roughness={0.45} />
    </mesh>
  );
}
function Link({ a, b }: { a: CncPoint; b: CncPoint }) {
  const start = new Vector3(...a),
    end = new Vector3(...b),
    delta = end.clone().sub(start);
  const q = new Quaternion().setFromUnitVectors(
    new Vector3(0, 1, 0),
    delta.clone().normalize(),
  );
  const geometry = useMemo(() => new CylinderGeometry(0.085, 0.11, 1, 12), []);
  return (
    <mesh
      position={start.add(end).multiplyScalar(0.5)}
      quaternion={q}
      scale={[1, delta.length(), 1]}
      geometry={geometry}
      castShadow
    >
      <meshStandardMaterial color="#bd914e" metalness={0.4} roughness={0.4} />
    </mesh>
  );
}
function Part({ machined }: { machined: boolean }) {
  const shape = useMemo(() => {
    const s = new Shape();
    s.moveTo(-0.25, -0.19);
    s.lineTo(0.25, -0.19);
    s.lineTo(0.25, 0.19);
    s.lineTo(-0.25, 0.19);
    s.closePath();
    const pocket = new Path();
    pocket.moveTo(-0.1, -0.11);
    pocket.lineTo(-0.1, 0.11);
    pocket.lineTo(0.1, 0.11);
    pocket.lineTo(0.1, -0.11);
    pocket.closePath();
    s.holes.push(pocket);
    for (const x of [-0.18, 0.18]) {
      const hole = new Path();
      hole.absarc(x, 0, 0.035, 0, Math.PI * 2, true);
      s.holes.push(hole);
    }
    return s;
  }, []);
  return (
    <group>
      <Box at={[0, -0.055, 0]} size={[0.5, 0.05, 0.38]} color="#9faeb8" />
      {machined ? (
        <mesh
          rotation={[-Math.PI / 2, 0, 0]}
          position={[0, -0.03, 0]}
          castShadow
        >
          <extrudeGeometry
            args={[
              shape,
              { depth: 0.12, bevelEnabled: false, curveSegments: 12 },
            ]}
          />
          <meshStandardMaterial
            color="#c6d3da"
            metalness={0.65}
            roughness={0.3}
          />
        </mesh>
      ) : (
        <Box at={[0, 0.03, 0]} size={[0.5, 0.12, 0.38]} color="#b4bfc6" />
      )}
    </group>
  );
}
export default function CncCell({ state }: { state: CncState }) {
  const pose = cncPose(state);
  const shoulder: CncPoint = [-1.04, 1.1, 0.1];
  // Two fixed-length links: solve an elbow in the vertical plane through the wrist.
  const direction = new Vector3(...pose.hand).sub(new Vector3(...shoulder));
  const distance = direction.length();
  direction.normalize();
  const upperLength = 1.2,
    lowerLength = 1.1;
  const along =
    (upperLength ** 2 - lowerLength ** 2 + distance ** 2) / (2 * distance);
  const bend = new Vector3(0, 1, 0)
    .addScaledVector(direction, -direction.y)
    .normalize();
  const elbow = new Vector3(...shoulder)
    .addScaledVector(direction, along)
    .addScaledVector(
      bend,
      Math.sqrt(Math.max(0, upperLength ** 2 - along ** 2)),
    )
    .toArray() as CncPoint;
  return (
    <group>
      <Box at={[0, 0.09, 0]} size={[2.7, 0.18, 2.5]} color="#344752" />
      {/* Open-front enclosure with a sliding, windowed door. */}
      <Box at={[0.3, 0.6, -0.35]} size={[1.8, 1, 1.55]} color="#d6dcda" />
      <Box at={[0.3, 2.05, -1.05]} size={[1.8, 1.9, 0.12]} />
      <Box at={[-0.56, 2, -0.35]} size={[0.12, 1.9, 1.5]} />
      <Box at={[1.16, 2, -0.35]} size={[0.12, 1.9, 1.5]} />
      <Box at={[0.3, 2.97, -0.35]} size={[1.84, 0.14, 1.55]} color="#344752" />
      <Box at={[0.25, 1.08, -0.3]} size={[0.85, 0.15, 0.7]} color="#526871" />
      {[-1, 1].map((sign) => (
        <Box
          key={sign}
          at={[0.25 + sign * (pose.clamped ? 0.3 : 0.41), 1.23, -0.3]}
          size={[0.1, 0.18, 0.42]}
          color="#526871"
        />
      ))}
      <group
        position={[
          state.phase === 5 ? 0.25 + Math.sin(state.elapsed * 3) * 0.12 : 0.25,
          state.phase === 5 ? 1.65 : 2.4,
          -0.3,
        ]}
      >
        <Box at={[0, 0.15, 0]} size={[0.34, 0.5, 0.36]} color="#526871" />
        <mesh
          position={[0, -0.21, 0]}
          rotation={[0, state.phase === 5 ? state.elapsed * 30 : 0, 0]}
        >
          <cylinderGeometry args={[0.035, 0.055, 0.24, 6]} />
          <meshStandardMaterial
            color="#b4bbc0"
            metalness={0.8}
            roughness={0.2}
          />
        </mesh>
      </group>
      {[-1, 1].map((sign) => (
        <group
          key={sign}
          position={[0.3 + sign * (0.37 + (1 - pose.door) * 0.64), 0, 0]}
        >
          <Box at={[0, 1.35, 0.47]} size={[0.74, 0.28, 0.07]} />
          <Box at={[0, 2.8, 0.47]} size={[0.74, 0.25, 0.07]} />
          {[-0.33, 0.33].map((x) => (
            <Box key={x} at={[x, 2.08, 0.47]} size={[0.08, 1.35, 0.07]} />
          ))}
          <mesh position={[0, 2.06, 0.47]}>
            <boxGeometry args={[0.59, 1.22, 0.03]} />
            <meshStandardMaterial
              color="#7eaaa8"
              transparent
              opacity={0.24}
              depthWrite={false}
            />
          </mesh>
          <Box
            at={[-sign * 0.24, 2, 0.55]}
            size={[0.045, 0.3, 0.07]}
            color="#344752"
          />
        </group>
      ))}
      <Box at={[-1.04, 0.6, 0.1]} size={[0.42, 1, 0.42]} color="#526871" />
      <Link a={shoulder} b={elbow} />
      <Link a={elbow} b={pose.hand} />
      {[shoulder, elbow, pose.hand].map((at, i) => (
        <mesh key={i} position={at} castShadow>
          <sphereGeometry args={[i === 2 ? 0.1 : 0.14, 16, 12]} />
          <meshStandardMaterial color="#344752" />
        </mesh>
      ))}
      <group position={pose.hand}>
        <Box at={[0, 0.18, 0]} size={[0.62, 0.1, 0.16]} color="#526871" />
        {[-1, 1].map((sign) => (
          <Box
            key={sign}
            at={[sign * (pose.location === "gripper" ? 0.28 : 0.34), 0.05, 0]}
            size={[0.05, 0.24, 0.12]}
            color="#344752"
          />
        ))}
      </group>
      <Box at={[-0.95, 0.89, 0.96]} size={[0.65, 0.14, 0.55]} color="#526871" />
      <Box at={[1.05, 1.32, 0.65]} size={[0.58, 0.2, 0.5]} color="#526871" />
      <group position={pose.block}>
        <Part machined={pose.machined} />
      </group>
      <Box
        at={[1.05, 3.12, -0.8]}
        size={[0.09, 0.22, 0.09]}
        color={
          state.alarm
            ? "#a35349"
            : state.mode === "running"
              ? "#589780"
              : "#bd914e"
        }
      />
    </group>
  );
}
