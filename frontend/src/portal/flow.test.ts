import Ajv from "ajv";
import { expect, it } from "vitest";
import flow from "../../../content/flow-map.json";
import schema from "../../../content/flow-map.schema.json";
import { help } from "../shared/content";
const validate = new Ajv({ strict: false }).compile(schema);
it("흐름 맵은 버전 1 JSON 스키마를 만족한다", () => {
  expect(validate(flow), JSON.stringify(validate.errors)).toBe(true);
});
it("알 수 없는 필드가 추가되면 계약 검증에 실패한다", () => {
  expect(validate({ ...flow, progress: 1 })).toBe(false);
});
it("도움말 없는 업무 노드는 스키마에서 거부한다", () => {
  const invalid = structuredClone(flow);
  (invalid.nodes[0] as { helpKey: string | null }).helpKey = null;
  expect(validate(invalid)).toBe(false);
});
it("노드 키는 중복되지 않는다", () => {
  expect(new Set(flow.nodes.map((n) => n.id)).size).toBe(18);
});
it("연결의 양 끝은 실제 노드로 존재한다", () => {
  const ids = new Set(flow.nodes.map((n) => n.id));
  expect(flow.edges.every((e) => ids.has(e.from) && ids.has(e.to))).toBe(true);
});
it("모든 업무 노드는 존재하는 맥락 도움말로 연결된다", () => {
  expect(
    flow.nodes
      .filter((n) => n.kind === "solution")
      .every((n) => !!n.helpKey && !!help[n.helpKey]),
  ).toBe(true);
});
it("설명 카드로 향하는 연결은 점선이다", () => {
  const cards = new Set(
    flow.nodes.filter((n) => n.kind === "card").map((n) => n.id),
  );
  expect(
    flow.edges.every(
      (e) =>
        e.kind === (cards.has(e.from) || cards.has(e.to) ? "card" : "solution"),
    ),
  ).toBe(true);
});
it("BEMS 분해 노드는 FEMS에서 실선으로 이어지는 업무 노드다(FS-025c)", () => {
  expect(flow.nodes).toContainEqual(
    expect.objectContaining({
      id: "building_energy",
      kind: "solution",
      helpKey: "bems/b-02",
    }),
  );
  expect(flow.edges).toContainEqual(
    expect.objectContaining({
      from: "energy_master",
      to: "building_energy",
      kind: "solution",
    }),
  );
});
it("QMS를 끄면 쓰는 실적-패킹 직결 경로를 보존한다", () => {
  expect(flow.edges).toContainEqual(
    expect.objectContaining({
      from: "operation_result",
      to: "packing",
      kind: "solution",
    }),
  );
});
