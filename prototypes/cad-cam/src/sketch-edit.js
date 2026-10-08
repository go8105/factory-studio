import {
  arcPoints,
  profileRing,
  syncProfile,
  validateProfile,
} from "./profile.js";
import { solveSketch } from "./sketch-constraints.js";
const copy = (s) => structuredClone(s);
const cross = (a, b) => a[0] * b[1] - a[1] * b[0];
export function asProfile(shape) {
  if (shape.type === "profile") return copy(shape);
  const s = {
    ...copy(shape),
    type: "profile",
    closed: true,
    angle: 0,
    constraints: [],
    nodes: [],
  };
  if (shape.type === "circle") {
    const r = shape.w / 2;
    s.nodes = [
      { id: "p1", point: [r, 0], arcVia: [0, r] },
      { id: "p2", point: [-r, 0], arcVia: [0, -r] },
    ];
  } else if (shape.type === "slot") {
    const r = shape.h / 2,
      a = (shape.w - shape.h) / 2;
    s.nodes = [
      { id: "p1", point: [-a, -r] },
      { id: "p2", point: [a, -r], arcVia: [a + r, 0] },
      { id: "p3", point: [a, r] },
      { id: "p4", point: [-a, r], arcVia: [-a - r, 0] },
    ];
    if (!a)
      s.nodes = [
        { id: "p1", point: [0, -r], arcVia: [r, 0] },
        { id: "p2", point: [0, r], arcVia: [-r, 0] },
      ];
  } else if (shape.type === "rect") {
    const x = shape.w / 2,
      y = shape.h / 2,
      r = shape.radius;
    if (!r)
      s.nodes = [
        [-x, -y],
        [x, -y],
        [x, y],
        [-x, y],
      ].map((point, i) => ({ id: "p" + (i + 1), point }));
    else {
      const c = Math.SQRT1_2 * r;
      s.nodes = [
        { point: [x - r, -y] },
        { point: [x, -y + r] },
        { point: [x, y - r] },
        { point: [x - r, y] },
        { point: [-x + r, y] },
        { point: [-x, y - r] },
        { point: [-x, -y + r] },
        { point: [-x + r, -y] },
      ];
      s.nodes[0].arcVia = [x - r + c, -y + r - c];
      s.nodes[2].arcVia = [x - r + c, y - r + c];
      s.nodes[4].arcVia = [-x + r - c, y - r + c];
      s.nodes[6].arcVia = [-x + r - c, -y + r - c];
      // Start each arc at its tangent point; the other four entities are straight sides.
      s.nodes.forEach((n, i) => (n.id = "p" + (i + 1)));
      // If a side vanishes, combine its adjacent tangent nodes into the existing arc start.
      s.nodes = s.nodes.filter(
        (n, i, all) =>
          Math.hypot(
            ...n.point.map((v, k) => v - all[(i + 1) % all.length].point[k]),
          ) > 1e-7,
      );
    }
  } else throw Error("지원하지 않는 스케치입니다.");
  const t = ((shape.angle ?? 0) * Math.PI) / 180,
    rotate = ([x, y]) => [
      x * Math.cos(t) - y * Math.sin(t),
      x * Math.sin(t) + y * Math.cos(t),
    ];
  s.nodes.forEach((n) => {
    n.point = rotate(n.point);
    if (n.arcVia) n.arcVia = rotate(n.arcVia);
  });
  s.radius = 0;
  return syncProfile(s);
}
export function free(s) {
  if (s.constraints?.length)
    throw Error("이 명령 전에 해당 와이어의 구속을 해제하세요.");
}
export function transformWire(input, ids, kind, args) {
  const s = copy(input);
  free(s);
  const selected = new Set(ids);
  if (!selected.size) throw Error("점을 선택하세요.");
  const [u, v, deg = 0] = args;
  if (!args.every(Number.isFinite)) throw Error("유효한 변형 값을 입력하세요.");
  const t = (deg * Math.PI) / 180;
  const move = ([x, y]) =>
    kind === "move"
      ? [x + u, y + v]
      : kind === "rotate"
        ? [
            u + (x - u) * Math.cos(t) - (y - v) * Math.sin(t),
            v + (x - u) * Math.sin(t) + (y - v) * Math.cos(t),
          ]
        : kind === "mirror-u"
          ? [x, 2 * v - y]
          : [2 * u - x, y];
  for (const n of s.nodes)
    if (selected.has(n.id)) {
      n.point = move(n.point);
      if (n.arcVia) n.arcVia = move(n.arcVia);
    }
  return syncProfile(s);
}
export function trimWire(input, id, ratio = 0.25) {
  const s = copy(input);
  free(s);
  const i = s.nodes.findIndex((n) => n.id === id);
  if (i < 0 || (!s.closed && i === s.nodes.length - 1))
    throw Error("나가는 선/원호가 있는 점을 선택하세요.");
  if (s.closed) {
    s.nodes = [...s.nodes.slice(i + 1), ...s.nodes.slice(0, i + 1)];
    delete s.nodes.at(-1).arcVia;
    s.closed = false;
  } else {
    if (s.nodes[i].arcVia || ![0, s.nodes.length - 2].includes(i))
      throw Error("열린 와이어의 첫/마지막 직선만 비율로 자를 수 있습니다.");
    if (!(ratio > 0 && ratio < 1))
      throw Error("자르기 비율은 0과 1 사이입니다.");
    const a = s.nodes[i].point,
      b = s.nodes[i + 1].point;
    if (i === 0) s.nodes[i].point = a.map((v, k) => v + (b[k] - v) * ratio);
    else s.nodes[i + 1].point = b.map((v, k) => v + (a[k] - v) * ratio);
  }
  return syncProfile(s);
}
export function extendWire(input, id, amount) {
  const s = copy(input);
  free(s);
  const i = s.nodes.findIndex((n) => n.id === id),
    last = s.nodes.length - 1;
  if (
    s.closed ||
    ![0, last].includes(i) ||
    last < 1 ||
    !(amount > 0 && amount <= 100)
  )
    throw Error("열린 와이어 끝점과 0~100mm 연장 길이를 선택하세요.");
  const n = s.nodes[i],
    other = s.nodes[i === 0 ? 1 : last - 1];
  if ((i === 0 ? n : other).arcVia)
    throw Error("직선 끝만 연장할 수 있습니다.");
  const len = Math.hypot(...n.point.map((v, k) => v - other.point[k]));
  if (len < 0.001) throw Error("퇴화한 선입니다.");
  n.point = n.point.map((v, k) => v + ((v - other.point[k]) * amount) / len);
  return syncProfile(s);
}
export function offsetWire(input, amount) {
  const s = copy(input);
  free(s);
  validateProfile(s);
  if (
    s.nodes.some((n) => n.arcVia) ||
    !Number.isFinite(amount) ||
    Math.abs(amount) > 100 ||
    !amount
  )
    throw Error("오프셋은 직선 볼록 윤곽과 0이 아닌 ±100mm만 지원합니다.");
  const p = s.nodes.map((n) => n.point),
    N = p.length;
  let area = 0;
  for (let i = 0; i < N; i++) area += cross(p[i], p[(i + 1) % N]);
  const sign = Math.sign(area);
  const lines = p.map((a, i) => {
    const b = p[(i + 1) % N],
      d = b.map((v, k) => v - a[k]),
      len = Math.hypot(...d);
    const next = p[(i + 2) % N].map((v, k) => v - b[k]);
    if (sign * cross(d, next) <= 1e-7)
      throw Error("엄격 볼록 윤곽만 오프셋 가능합니다.");
    return {
      a: [
        a[0] + ((sign * d[1]) / len) * amount,
        a[1] - ((sign * d[0]) / len) * amount,
      ],
      d,
    };
  });
  s.nodes.forEach((n, i) => {
    const a = lines[(i + N - 1) % N],
      b = lines[i],
      t =
        cross(
          b.a.map((v, k) => v - a.a[k]),
          b.d,
        ) / cross(a.d, b.d);
    n.point = a.a.map((v, k) => v + t * a.d[k]);
  });
  // A large inward offset can invert each edge without a self-intersection.
  for (let i = 0; i < N; i++) {
    const d = s.nodes[(i + 1) % N].point.map((v, k) => v - s.nodes[i].point[k]);
    if (d[0] * lines[i].d[0] + d[1] * lines[i].d[1] <= 1e-7)
      throw Error("오프셋으로 윤곽이 소멸했습니다.");
  }
  syncProfile(s);
  validateProfile(s);
  return s;
}
export function measureEntity(s, id) {
  const i = s.nodes.findIndex((n) => n.id === id),
    a = s.nodes[i],
    b = s.nodes[(i + 1) % s.nodes.length];
  if (!a || !b || (!s.closed && i === s.nodes.length - 1)) return null;
  const chord = Math.hypot(...a.point.map((v, k) => v - b.point[k]));
  if (!a.arcVia) return { kind: "선", length: chord };
  const p = [...arcPoints(a.point, a.arcVia, b.point), b.point];
  const u = a.arcVia.map((v, k) => v - a.point[k]),
    v = b.point.map((v, k) => v - a.point[k]);
  const radius =
    (Math.hypot(...u) *
      Math.hypot(...v) *
      Math.hypot(...a.arcVia.map((x, k) => x - b.point[k]))) /
    (2 * Math.abs(cross(u, v)));
  // Arc tessellation has uniform angular increments; recover its exact central angle.
  const stepChord = Math.hypot(...p[1].map((v, k) => v - p[0][k]));
  const length =
    radius *
    2 *
    Math.asin(Math.min(1, stepChord / (2 * radius))) *
    (p.length - 1);
  return { kind: "원호", length, radius, chord };
}
export function constrain(input, c) {
  const s = copy(input);
  s.constraints ??= [];
  s.constraints.push(c);
  return solveSketch(s).sketch;
}
