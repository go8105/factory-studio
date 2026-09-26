function Part({
  at,
  size,
  color = "#465965",
}: {
  at: [number, number, number];
  size: [number, number, number];
  color?: string;
}) {
  return (
    <mesh position={at} castShadow receiveShadow>
      <boxGeometry args={size} />
      <meshStandardMaterial color={color} roughness={0.65} metalness={0.15} />
    </mesh>
  );
}
export default function Workshop() {
  return (
    <group>
      {[0, 4, 8].map((x) => (
        <group key={x} position={[x, 0, -5]}>
          {[-1, 1].map((side) => (
            <Part key={side} at={[side, 1.45, 0]} size={[0.09, 2.9, 1.1]} />
          ))}
          {[0.2, 1.35, 2.5].map((y) => (
            <group key={y}>
              <Part at={[0, y, 0]} size={[2.1, 0.1, 1.1]} color="#b0b6b0" />
              {[-0.55, 0.55].map((dx) => (
                <group key={dx}>
                  <Part
                    at={[dx, y + 0.28, 0]}
                    size={[0.8, 0.48, 0.8]}
                    color="#a78e6c"
                  />
                  <Part
                    at={[dx, y + 0.3, 0.405]}
                    size={[0.32, 0.15, 0.012]}
                    color="#e1dfd4"
                  />
                </group>
              ))}
            </group>
          ))}
        </group>
      ))}
      <group position={[-1, 0, -3.7]}>
        <Part at={[0, 0.85, 0]} size={[1.3, 0.1, 0.65]} color="#a6b6b4" />
        {[-0.5, 0.5].map((x) => (
          <Part key={x} at={[x, 0.4, 0]} size={[0.1, 0.8, 0.6]} />
        ))}
        <Part at={[0, 1.45, -0.3]} size={[1.3, 1.1, 0.06]} />
        {[-0.4, -0.2, 0, 0.2, 0.4].map((x) => (
          <Part
            key={x}
            at={[x, 1.5, -0.25]}
            size={[0.055, 0.36, 0.04]}
            color="#bac1bc"
          />
        ))}
      </group>
      <group position={[10.4, 0, -3.3]}>
        <Part at={[0, 0.8, 0]} size={[0.65, 1.6, 0.55]} color="#a44437" />
        <Part at={[0, 1.2, 0.29]} size={[0.38, 0.3, 0.015]} color="#f0eee6" />
      </group>
    </group>
  );
}
