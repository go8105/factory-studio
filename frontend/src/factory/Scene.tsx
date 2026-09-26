import ProductionCell from "./ProductionCell";
import Workshop from "./Workshop";
import { FactoryEnvironment, FactoryFloor } from "./Surface";
import Building from "./Building";
import VisionCell from "./VisionCell";
import type { VisionSnapshot } from "./vision";
import { useEffect, useRef, type RefObject } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { Html, OrbitControls } from "@react-three/drei";
import { Group, Vector3 } from "three";
import {
  inputVector,
  move,
  stations,
  type Direction,
  type Point,
  type View,
} from "./world";

type Vec = [number, number, number];
const colors = {
  wall: "#e0e5e3",
  teal: "#467e7c",
  dark: "#293c49",
  floor: "#c8cfcb",
  yellow: "#d6ad59",
};
function Box({
  at,
  size,
  color = colors.wall,
  rotate = 0,
}: {
  at: Vec;
  size: Vec;
  color?: string;
  rotate?: number;
}) {
  return (
    <mesh position={at} rotation={[0, rotate, 0]} castShadow receiveShadow>
      <boxGeometry args={size} />
      <meshStandardMaterial color={color} roughness={0.75} />
    </mesh>
  );
}
function Label({ at, children }: { at: Vec; children: React.ReactNode }) {
  return (
    <Html
      position={at}
      center
      occlude
      zIndexRange={[20, 0]}
      style={{ pointerEvents: "none" }}
    >
      <span className="factory-label">{children}</span>
    </Html>
  );
}
function Person({
  at,
  seated = false,
  walking = false,
  animated,
  visitor = false,
  moving,
}: {
  at: Vec;
  seated?: boolean;
  walking?: boolean;
  animated: boolean;
  visitor?: boolean;
  moving?: RefObject<boolean>;
}) {
  const limbs = useRef<Group>(null);
  useFrame(({ clock }) => {
    if (!limbs.current) return;
    const wave =
      animated && (moving?.current ?? true)
        ? Math.sin(clock.elapsedTime * (walking ? 6 : 4))
        : 0;
    limbs.current.children.forEach((limb, i) => {
      limb.rotation.x = seated
        ? 1.1 + (i < 2 ? 0 : wave * 0.08)
        : walking
          ? wave * (i % 2 ? 0.5 : -0.5)
          : 0;
    });
  });
  const shirt = visitor ? "#d8a453" : colors.teal;
  return (
    <group position={at}>
      <Box
        at={[0, seated ? 0.92 : 1.02, 0]}
        size={[0.5, 0.6, 0.32]}
        color={shirt}
      />
      <mesh position={[0, seated ? 1.45 : 1.55, 0]} castShadow>
        <sphereGeometry args={[0.22, 12, 10]} />
        <meshStandardMaterial color="#d4b69a" />
      </mesh>
      {!seated && (
        <mesh position={[0, 1.71, 0]} castShadow>
          <sphereGeometry
            args={[0.24, 12, 8, 0, Math.PI * 2, 0, Math.PI / 2]}
          />
          <meshStandardMaterial color={visitor ? "#f3e4bd" : "#ecede5"} />
        </mesh>
      )}
      <group ref={limbs}>
        {[-0.14, 0.14].map((x) => (
          <group key={`leg${x}`} position={[x, seated ? 0.65 : 0.73, 0]}>
            <Box
              at={[0, -0.32, 0]}
              size={[0.18, 0.64, 0.2]}
              color={colors.dark}
            />
          </group>
        ))}
        {[-0.34, 0.34].map((x) => (
          <group key={`arm${x}`} position={[x, seated ? 1.15 : 1.26, 0]}>
            <Box at={[0, -0.24, 0]} size={[0.14, 0.48, 0.16]} color={shirt} />
          </group>
        ))}
      </group>
      {visitor && (
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.025, 0]}>
          <ringGeometry args={[0.36, 0.46, 28]} />
          <meshBasicMaterial color={colors.yellow} />
        </mesh>
      )}
    </group>
  );
}
function Desk({ at, animated }: { at: Vec; animated: boolean }) {
  return (
    <group position={at}>
      <Box at={[0, 0.95, 0]} size={[2.5, 0.12, 1.2]} color="#bbaa8b" />
      {[-1.05, 1.05].flatMap((x) =>
        [-0.4, 0.4].map((z) => (
          <Box
            key={`${x}${z}`}
            at={[x, 0.46, z]}
            size={[0.08, 0.92, 0.08]}
            color={colors.dark}
          />
        )),
      )}
      <Box at={[0, 1.05, 0.1]} size={[0.8, 0.06, 0.5]} color={colors.dark} />
      <Box at={[0, 1.35, -0.16]} size={[0.8, 0.52, 0.06]} color={colors.dark} />
      <Box at={[0, 1.35, -0.12]} size={[0.69, 0.4, 0.01]} color="#89bdbb" />
      <Box at={[0, 0.54, 0.95]} size={[0.65, 0.12, 0.6]} color={colors.dark} />
      <Box at={[0, 0.9, 1.22]} size={[0.65, 0.75, 0.1]} color={colors.dark} />
      <Box at={[0, 0.28, 0.95]} size={[0.1, 0.56, 0.1]} color={colors.dark} />
      <Person at={[0, 0, 0.86]} seated animated={animated} />
    </group>
  );
}
function Printer({ label }: { label: boolean }) {
  return (
    <group position={[-8, 0, 0]}>
      <Box at={[0, 0.8, 0]} size={[2.2, 1.6, 0.8]} color="#c1c8c2" />
      <Box at={[0, 1.85, 0]} size={[0.9, 0.5, 0.65]} color={colors.dark} />
      <Box at={[0, 1.71, 0.43]} size={[0.5, 0.03, 0.48]} color="white" />
      {Array.from({ length: 9 }, (_, i) => (
        <Box
          key={i}
          at={[-0.2 + i * 0.046, 1.731, 0.45]}
          size={[i % 3 ? 0.018 : 0.03, 0.01, 0.22]}
          color={colors.dark}
        />
      ))}
      {label && <Label at={[0, 2.55, 0]}>바코드 프린터</Label>}
    </group>
  );
}
function Station({
  index,
  onSelect,
  animated,
  fault,
  onSnapshot,
}: {
  animated: boolean;
  fault: boolean;
  onSnapshot: (value: VisionSnapshot) => void;
  index: number;
  onSelect: (i: number) => void;
}) {
  const { x } = stations[index];
  return (
    <group position={[x, 0, 0]}>
      <group
        onClick={(event) => {
          event.stopPropagation();
          onSelect(index);
        }}
      >
        {index === 1 ? (
          <VisionCell
            animated={animated}
            fault={fault}
            onSnapshot={onSnapshot}
          />
        ) : (
          <ProductionCell index={index} animated={animated} />
        )}
      </group>
      <group position={[1.25, 0, 2]}>
        <Box at={[0, 0.68, 0]} size={[0.16, 1.36, 0.16]} color={colors.dark} />
        <Box at={[0, 1.6, 0]} size={[0.7, 0.55, 0.15]} color={colors.dark} />
        <Box at={[0, 1.6, 0.085]} size={[0.6, 0.44, 0.02]} color="#8cb9b3" />
        <Box at={[0, 1.65, 0.1]} size={[0.42, 0.03, 0.01]} color="#e8efea" />
      </group>
      <Label at={[0, 3.65, 0]}>{stations[index].name}</Label>
    </group>
  );
}
function Products({ animated }: { animated: boolean }) {
  const group = useRef<Group>(null);
  const time = useRef(0);
  useFrame((_, dt) => {
    if (animated) time.current += Math.min(dt, 0.05);
    group.current?.children.forEach((box, i) => {
      box.position.x = -1.4 + ((time.current * 0.65 + i * 2.3) % 11);
      box.visible =
        (box.position.x > 1 && box.position.x < 2.5) ||
        (box.position.x > 5.5 && box.position.x < 7) ||
        box.position.x > 9.95;
    });
  });
  return (
    <group ref={group}>
      {[0, 1, 2, 3].map((i) => (
        <Box
          key={i}
          at={[-1.4 + i * 2.3, 1.51, 0]}
          size={[0.45, 0.25, 0.5]}
          color="#bca279"
        />
      ))}
    </group>
  );
}
function Worker({ animated }: { animated: boolean }) {
  const group = useRef<Group>(null);
  const moving = useRef(false);
  const point = useRef({ x: -1.9, z: -2.8 });
  const segment = useRef(0);
  const pause = useRef(0);
  const route = [
    [4, -2.8],
    [10.35, -2.8],
    [10.35, 4.2],
    [-1.9, 4.2],
    [-1.9, -2.8],
  ];
  useFrame((_, dt) => {
    if (!group.current) return;
    const step = Math.min(dt, 0.05);
    moving.current = animated && pause.current <= 0;
    if (animated && pause.current > 0) pause.current -= step;
    if (moving.current) {
      const target = route[segment.current];
      const dx = target[0] - point.current.x;
      const dz = target[1] - point.current.z;
      const length = Math.hypot(dx, dz);
      if (length < 0.06) {
        segment.current = (segment.current + 1) % route.length;
        pause.current = 2;
      } else {
        point.current.x += (dx / length) * step * 0.9;
        point.current.z += (dz / length) * step * 0.9;
        group.current.rotation.y = Math.atan2(-dx, -dz);
      }
    }
    group.current.position.set(point.current.x, 0, point.current.z);
  });
  return (
    <group ref={group}>
      <Person at={[0, 0, 0]} walking moving={moving} animated={animated} />
    </group>
  );
}
export type SceneProps = {
  onReady: () => void;
  exterior: boolean;
  fault: boolean;
  onSnapshot: (value: VisionSnapshot) => void;
  focused: boolean;
  view: View;
  walking: boolean;
  animated: boolean;
  position: RefObject<Point>;
  keys: RefObject<Set<Direction>>;
  reset: number;
  onSelect: (i: number) => void;
};
export default function Scene({
  onReady,
  exterior,
  fault,
  onSnapshot,
  focused,
  view,
  walking,
  animated,
  position,
  keys,
  reset,
  onSelect,
}: SceneProps) {
  const { camera, size } = useThree();
  useEffect(() => {
    onReady();
  }, [onReady]);
  const avatar = useRef<Group>(null);
  const moving = useRef(false);
  const upper = useRef<Group>(null);
  const controls = useRef<React.ComponentRef<typeof OrbitControls>>(null);
  const look = useRef(new Vector3());
  useEffect(() => {
    if (!walking) {
      const office = view === "office";
      camera.position.set(
        ...((office
          ? [-1, 16, 20]
          : view === "ground"
            ? [6, 20, 28]
            : [23, 22, 28]) as Vec),
      );
      if (exterior) camera.position.set(29, 23, 33);
      else if (focused) camera.position.set(8, 5, 7);
      camera.position.multiplyScalar(Math.max(1, size.height / size.width));
      controls.current?.target.set(
        exterior ? 0 : focused ? 4 : office ? -7 : 0,
        exterior ? 3 : focused ? 1.7 : office ? 4 : 0.5,
        0,
      );
      controls.current?.update();
    }
  }, [
    view,
    walking,
    reset,
    camera,
    size.width,
    size.height,
    focused,
    exterior,
  ]);
  useFrame((_, dt) => {
    if (upper.current)
      upper.current.visible = walking
        ? position.current.y > 2
        : view !== "ground";
    if (!walking || !avatar.current) return;
    const delta = inputVector(keys.current, dt);
    position.current = move(position.current, delta.x, delta.z);
    const p = position.current;
    moving.current = !!(delta.x || delta.z);
    avatar.current.position.set(p.x, p.y, p.z);
    if (delta.x || delta.z)
      avatar.current.rotation.y = Math.atan2(-delta.x, -delta.z);
    const blend = 1 - Math.exp(-6 * Math.min(dt, 0.05));
    camera.position.lerp(new Vector3(p.x, p.y + 4.6, p.z + 7), blend);
    look.current.lerp(new Vector3(p.x, p.y + 1, p.z - 1), blend);
    camera.lookAt(look.current);
  });
  return (
    <>
      <color attach="background" args={["#e8ece8"]} />
      <FactoryEnvironment />
      <ambientLight intensity={0.45} />
      <directionalLight
        position={[5, 22, 10]}
        intensity={2.6}
        castShadow
        shadow-mapSize={[2048, 2048]}
        shadow-camera-left={-24}
        shadow-camera-right={24}
        shadow-camera-top={22}
        shadow-camera-bottom={-22}
        shadow-bias={-0.001}
      />
      <hemisphereLight args={["#e8f0f4", "#a2aaa2", 0.7]} />
      <Box at={[0, -0.25, 0]} size={[23, 0.5, 15]} color={colors.floor} />
      <FactoryFloor />
      <Building exterior={exterior} walking={walking} />
      <group visible={!exterior}>
        <Workshop />
        <Box at={[-3, 1.7, -2.5]} size={[0.14, 3.4, 9]} color="#b8c8c3" />
        <Box at={[-7.2, 0.015, -2]} size={[8, 0.025, 9.7]} color="#dad5c8" />
        <Desk at={[-8, 0, -3.5]} animated={animated} />
        <Printer label={view === "ground" && !walking} />
        {view === "ground" && !walking && (
          <Label at={[-7.3, 2.7, 2]}>1F 현장사무실</Label>
        )}
        <Label at={[4.5, 0.25, 5.6]}>생산 현장 · 조립 → 검사 → 포장</Label>
        {[1.75, 6.25].map((x) => (
          <Box
            key={x}
            at={[x, 1.3, 0]}
            size={[1.9, 0.15, 0.9]}
            color={colors.dark}
          />
        ))}
        {[0, 1, 2].map((i) => (
          <Station
            key={i}
            index={i}
            onSelect={onSelect}
            animated={animated}
            fault={fault}
            onSnapshot={onSnapshot}
          />
        ))}
        <Products animated={animated} />
        <Worker animated={animated} />
        {Array.from({ length: 22 }, (_, i) => (
          <Box
            key={i}
            at={[-1.4 + i * 0.55, 0.03, 3.2]}
            size={[0.32, 0.025, 0.06]}
            color={colors.yellow}
          />
        ))}
        <Box
          at={[4, 0.02, -3.4]}
          size={[13, 0.02, 0.07]}
          color={colors.yellow}
        />
        {/* Office floor keeps the existing stairwell opening. */}
        <group ref={upper}>
          <Box at={[-8, 3.86, 0]} size={[6, 0.28, 14]} color="#ded8ca" />
          <Box at={[-4, 3.86, -2.5]} size={[2, 0.28, 9]} color="#ded8ca" />
          <Box at={[-4, 3.86, 6.5]} size={[2, 0.28, 1]} color="#ded8ca" />
          <Desk at={[-8, 4, -3.5]} animated={animated} />
          <Desk at={[-8, 4, 1]} animated={animated} />
          {view !== "ground" && !walking && (
            <Label at={[-7.5, 7, -3]}>2F 사무실 · 직원 2명</Label>
          )}
          <Box
            at={[-3.05, 4.9, -2.5]}
            size={[0.08, 0.08, 9]}
            color={colors.dark}
          />
          {[-6, -4, -2, 0, 1.8].map((z) => (
            <Box
              key={z}
              at={[-3.05, 4.45, z]}
              size={[0.05, 0.9, 0.05]}
              color={colors.dark}
            />
          ))}
        </group>
        {Array.from({ length: 16 }, (_, i) => (
          <Box
            key={i}
            at={[-4.15, (i + 1) * 0.125, 5.875 - i * 0.25]}
            size={[1.7, (i + 1) * 0.25, 0.25]}
            color="#adb8b3"
          />
        ))}
        <Label at={[-4.2, 0.35, 6.7]}>↑ 2F 계단</Label>
        {walking && (
          <group
            ref={avatar}
            position={[
              position.current.x,
              position.current.y,
              position.current.z,
            ]}
          >
            <Person
              at={[0, 0, 0]}
              visitor
              walking
              moving={moving}
              animated={animated}
            />
          </group>
        )}
      </group>
      {!walking && (
        <OrbitControls
          ref={controls}
          makeDefault
          minDistance={10}
          maxDistance={85}
          maxPolarAngle={Math.PI / 2.2}
          target={[
            exterior ? 0 : focused ? 4 : view === "office" ? -7 : 0,
            exterior ? 3 : focused ? 1.7 : view === "office" ? 4 : 0.5,
            0,
          ]}
        />
      )}
    </>
  );
}
