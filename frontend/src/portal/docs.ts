// P-05 참고 문서 구조 (DOC-01 §3~5). 구역은 경로 앞부분, 순서는 파일명, 제목은 첫 줄에서 얻는다.
// 사용자 참고 문서 트리는 새로 정의하지 않고 솔루션 메뉴 배열의 group을 그대로 쓴다.
import type { Screen } from "../shared/SolutionLayout";
import { mesScreens } from "../mes/MesLayout";
import { erpScreens } from "../erp/ErpLayout";
import { femsScreens } from "../fems/FemsLayout";
import { qmsScreens } from "../qms/QmsLayout";
import { wmsScreens } from "../wms/WmsLayout";
import { bemsScreens } from "../bems/BemsLayout";
import { gwScreens } from "../gw/GwLayout";
import { spcScreens } from "../spc/SpcLayout";
import { contentTitle } from "../shared/content";
export { slug } from "../shared/content";
export type DocGroup = { solution?: string; title: string; keys: string[] };
export type DocSection = {
  key: string;
  title: string;
  summary: string;
  groups: DocGroup[];
};
type Docs = Record<string, string>;
const solutions: [string, string, Screen[]][] = [
  ["mes", "MES 생산관리", mesScreens],
  ["erp", "ERP 경영관리", erpScreens],
  ["fems", "FEMS 에너지관리", femsScreens],
  ["qms", "QMS 품질관리", qmsScreens],
  ["wms", "WMS 창고관리", wmsScreens],
  ["bems", "BEMS 건물관리", bemsScreens],
  ["spc", "SPC 공정관리", spcScreens],
  ["gw", "GW 그룹웨어", gwScreens],
];
// 첫 화면 "많이 찾는 문서". 없는 키는 건너뛴다.
export const popular = [
  "design/d-01",
  "design/d-08",
  "design/d-02",
  "guide/s-01",
  "erp/e-10",
  "fems/f-06",
];
// 구역 순서는 평가자 우선순위(DOC-01 §3). 문서가 없는 구역은 보이지 않는다.
export function docSections(docs: Docs): DocSection[] {
  const under = (prefix: string) =>
    Object.keys(docs)
      .filter((k) => k.startsWith(prefix))
      .sort();
  const flat = (key: string, title: string, summary: string) => ({
    key,
    title,
    summary,
    groups: [{ title, keys: under(`${key}/`) }],
  });
  const reference: DocGroup[] = [
    {
      solution: "포털",
      title: "포털",
      keys: ["common", ...under("portal/")].filter((k) =>
        Object.hasOwn(docs, k),
      ),
    },
  ];
  for (const [prefix, name, screens] of solutions)
    for (const s of screens) {
      const key = `${prefix}/${s.id.toLowerCase()}`;
      if (!Object.hasOwn(docs, key)) continue;
      let group = reference.find(
        (g) => g.solution === name && g.title === s.group,
      );
      if (!group)
        reference.push((group = { solution: name, title: s.group, keys: [] }));
      group.keys.push(key);
    }
  return [
    flat("design", "설계 문서", "무엇을 왜 이렇게 만들었나 — 결정·대안·한계"),
    flat("guide", "업무 따라하기", "게스트 데이터로 업무를 처음부터 끝까지"),
    {
      key: "reference",
      title: "사용자 참고 문서",
      summary: "화면마다 하는 일과 막히는 지점",
      groups: reference,
    },
    flat("concept", "개념·용어", "제조·회계·에너지 용어를 이 제품 기준으로"),
  ].filter((s) => s.groups.some((g) => g.keys.length));
}
export const sectionOf = (sections: DocSection[], key: string) =>
  sections.find((s) => s.groups.some((g) => g.keys.includes(key)));
// 업무 화면 문서만 실제 화면 경로를 갖는다. 포털 문서는 연결하지 않는다.
export function screenPath(key: string) {
  if (key === "portal/cnc-cell") return "/factory";
  if (key === "portal/vision-lab") return "/factory/vision-lab";
  const [prefix, id] = key.split("/");
  const screen = solutions
    .find(([p]) => p === prefix)?.[2]
    .find((s) => s.id.toLowerCase() === id);
  return screen && `/${prefix}/${screen.path}`;
}
export const headings = (body: string) =>
  [...body.matchAll(/^## (.+)$/gm)].map((m) => m[1].trim());
const plain = (line: string) =>
  line
    .replace(/[#*`>|]/g, "")
    .replace(/^\s*(-|\d+\.)\s+/, "")
    .trim();
// ponytail: 부분 문자열 일치. 띄어쓰기가 다르면 못 찾는다. 문서가 수백 개면 색인으로 바꾼다.
export function searchDocs(docs: Docs, query: string) {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  return Object.entries(docs)
    .flatMap(([key, body]) => {
      const title = contentTitle(body);
      const inTitle = title.toLowerCase().includes(q);
      const line = body
        .split("\n")
        .slice(1)
        .filter((l) => !l.startsWith("<!--"))
        .find((l) => l.toLowerCase().includes(q));
      return inTitle || line
        ? [{ key, title, inTitle, snippet: line ? plain(line) : "" }]
        : [];
    })
    .sort((a, b) => Number(b.inTitle) - Number(a.inTitle));
}
