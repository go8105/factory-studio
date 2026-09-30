// Synthetic exterior truck. Progress is controlled by the server-backed arrival panel.
export default function Truck({ progress }: { progress: number }) {
  return (
    <group position={[24 - 17 * progress, 0, 10.5]} rotation={[0, Math.PI, 0]}>
      <mesh position={[-1.1, 1.25, 0]} castShadow>
        <boxGeometry args={[3.7, 2.1, 1.9]} />
        <meshStandardMaterial color="#dfe4e6" />
      </mesh>
      <mesh position={[1.6, 0.9, 0]} castShadow>
        <boxGeometry args={[1.7, 1.4, 1.9]} />
        <meshStandardMaterial color="#526f80" />
      </mesh>
      <mesh position={[1.7, 1.7, 0]}>
        <boxGeometry args={[1.25, 0.45, 1.82]} />
        <meshStandardMaterial color="#354954" />
      </mesh>
      {[-2, 1.7].flatMap((x) =>
        [-1, 1].map((z) => (
          <mesh
            key={`${x}:${z}`}
            position={[x, 0.45, z]}
            rotation={[Math.PI / 2, 0, 0]}
            castShadow
          >
            <cylinderGeometry args={[0.43, 0.43, 0.22, 16]} />
            <meshStandardMaterial color="#242a30" />
          </mesh>
        )),
      )}
    </group>
  );
}
