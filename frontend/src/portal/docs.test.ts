// DOC-01 참고 문서 구조·검색 계약
import { expect, it } from "vitest";
import { help } from "../shared/content";
import { docSections, screenPath, searchDocs, sectionOf } from "./docs";
it("모든 문서는 어느 구역의 트리에 속한다(고아 문서 0)", () => {
  const sections = docSections(help);
  expect(Object.keys(help).filter((k) => !sectionOf(sections, k))).toEqual([]);
});
it("참고 문서 트리는 메뉴 group 순서를 따른다", () => {
  const erp = docSections(help)
    .find((s) => s.key === "reference")!
    .groups.filter((g) => g.solution === "ERP 경영관리");
  expect(erp.map((g) => g.title)).toEqual([
    "개요",
    "영업",
    "출하·매출",
    "채권·수금",
    "매입·채무",
    "회계",
    "기준정보",
  ]);
});
it("문서가 없는 구역은 보이지 않고, 새 폴더는 파일명 순서로 구역이 된다", () => {
  const docs = {
    "design/d-02": "# 둘",
    "design/d-01": "# 하나",
    "erp/e-09": "# 매출채권 현황",
  };
  const sections = docSections(docs);
  expect(sections.map((s) => s.key)).toEqual(["design", "reference"]);
  expect(sections[0].groups[0].keys).toEqual(["design/d-01", "design/d-02"]);
});
it("화면 경로는 업무 화면 문서에만 있다", () => {
  expect(screenPath("mes/m-04")).toBe("/mes/lots");
  expect(screenPath("portal/p-02")).toBeUndefined();
  expect(screenPath("design/d-01")).toBeUndefined();
  expect(screenPath("flow/f-01")).toBe("/work-os/my-tasks");
  expect(screenPath("flow/f-02")).toBe("/work-os/boards");
  for (const [id, path] of [
    ["h-16", "work"],
    ["h-17", "work-demo"],
    ["h-18", "users"],
  ]) {
    expect(help[`hr/${id}`]).toBeTruthy();
    expect(screenPath(`hr/${id}`)).toBe(`/hr/${path}`);
  }
});
it("검색은 대소문자를 무시하고 제목 일치를 먼저, 출처 주석은 제외한다", () => {
  const docs = {
    a: "# 수금 안내\n본문",
    b: "# 다른 문서\n- **LOT** 과 수금을 잇는다",
    c: "# 세 번째\n<!-- sources: 수금 -->",
  };
  expect(searchDocs(docs, "수금")).toEqual([
    { key: "a", title: "수금 안내", inTitle: true, snippet: "" },
    {
      key: "b",
      title: "다른 문서",
      inTitle: false,
      snippet: "LOT 과 수금을 잇는다",
    },
  ]);
  expect(searchDocs(docs, "lot").map((r) => r.key)).toEqual(["b"]);
  expect(searchDocs(docs, "  ")).toEqual([]);
});
it("합성 검사 사용법은 사용자 참고 문서에 속하고 검사실로 연결된다", () => {
  expect(sectionOf(docSections(help), "portal/vision-lab")?.key).toBe(
    "reference",
  );
  expect(screenPath("portal/vision-lab")).toBe("/factory/vision-lab");
  expect(
    searchDocs(help, "C++").some((d) => d.key === "portal/vision-lab"),
  ).toBe(true);
});

it("CAD·CAM과 공장 안내는 검색·목차·실제 작업 화면에 연결된다", () => {
  const paths = {
    "portal/cad-cam": "/cad-cam",
    "portal/part-design": "/cad-cam?view=part",
    "portal/nc-review": "/cad-cam?view=nc",
    "portal/hugh-d": "/cad-cam?view=nc",
    "portal/factory": "/factory",
  };
  for (const [key, path] of Object.entries(paths)) {
    expect(help[key]).toBeTruthy();
    expect(sectionOf(docSections(help), key)?.key).toBe("reference");
    expect(screenPath(key)).toBe(path);
  }
  expect(
    searchDocs(help, "kWh").some((d) => d.key === "portal/nc-review"),
  ).toBe(true);
  expect(
    searchDocs(help, "헤이 휴디").some((d) => d.key === "portal/hugh-d"),
  ).toBe(true);
});
