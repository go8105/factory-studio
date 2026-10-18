// GW-READY-01 proposal workbook; never modifies current/target schema workbooks.
import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(path.join(root, "work/db-design/package.json"));
const { Workbook, SpreadsheetFile } = require("@oai/artifact-tool");
const data = JSON.parse(
  await fs.readFile(
    path.join(root, "docs/modules/gw/review/schema-proposal.json"),
    "utf8",
  ),
);
const wb = Workbook.create();
const sheets = [];
function add(name, title, heads, rows, widths) {
  const sh = wb.worksheets.add(name);
  sheets.push({ name, heads, rows, widths });
  sh.showGridLines = false;
  sh.getRange("A2").values = [[title]];
  sh.getRange("A3").values = [
    ["GW-READY-01 / 2026-10-18 / 전체 설계 확인 대상 · DB/제품 미적용"],
  ];
  sh.getRangeByIndexes(4, 0, 1, heads.length).values = [heads];
  if (rows.length)
    sh.getRangeByIndexes(5, 0, rows.length, heads.length).values = rows;
  const used = sh.getRangeByIndexes(0, 0, rows.length + 5, heads.length);
  used.format.font = { name: "Arial", size: 11, color: "#1A1C1E" };
  used.format.verticalAlignment = "center";
  sh.getRange("A2").format.font = {
    name: "Arial",
    size: 16,
    bold: true,
    color: "#1F2D3D",
  };
  sh.getRangeByIndexes(4, 0, 1, heads.length).format = {
    fill: "#1F2D3D",
    font: { name: "Arial", size: 11, bold: true, color: "#FFFFFF" },
    rowHeight: 32,
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
  };
  widths.forEach(
    (width, j) =>
      (sh.getRangeByIndexes(0, j, rows.length + 5, 1).format.columnWidth =
        width),
  );
  rows.forEach((row, i) => {
    const longest = Math.max(
      ...row.map((v, j) =>
        Math.ceil(String(v ?? "").length / Math.max(12, widths[j] * 0.75)),
      ),
    );
    sh.getRangeByIndexes(i + 5, 0, 1, heads.length).format = {
      wrapText: true,
      rowHeight: Math.max(34, Math.min(240, longest * 19 + 12)),
      verticalAlignment: "center",
      fill: i % 2 ? "#F7F7F6" : "#FFFFFF",
    };
  });
  sh.freezePanes.freezeRows(5);
}
add(
  "00_범위",
  "GW 보안·운영 DB 개정안",
  ["구분", "기준", "구현 상태"],
  [
    [
      "현재 실제 명세",
      "schema0.27 / 210표 / gw_wms_merge",
      "이번 검토에서 변경 없음",
    ],
    [
      "신규 제안",
      "core5표 + GW4표 = 신규9표",
      "미적용 · 이 파일을 실제 DB로 세지 않음",
    ],
    [
      "기존 표 확장 제안",
      "core.app_user / core.auth_session",
      "추가6컬럼·소유권 복합UK/FK 제안",
    ],
    ["초기 회사", "회사1 / 부서1 / 관리자1+직원9", "제품 최대 인원 한도 아님"],
    [
      "원문 기준",
      "docs/modules/gw/보안운영_DB_API_GW-READY-01.md",
      "세부 입력/권한·기간·멱등/비밀 계약",
    ],
    [
      "승인/구현",
      "전체 설계 확인 후 GW-READY-02 A~E",
      "기존 제품·실제 계정·DB 변경 없음",
    ],
  ],
  [26, 76, 62],
);
for (const [module, prefix] of [
  ["core", "CORE"],
  ["gw", "GW"],
]) {
  const tables = data.tables.filter((t) => t.name.startsWith(module + "."));
  add(
    prefix + "_테이블",
    prefix + " 개정 대상",
    ["테이블", "설명", "구분", "명세 컬럼 수"],
    tables.map((t) => [t.name, t.label, t.status, t.columns.length]),
    [42, 30, 47, 19],
  );
  add(
    prefix + "_컬럼",
    prefix + " 제안 컬럼",
    ["테이블", "컬럼", "타입", "NULL", "기본값", "설명"],
    tables.flatMap((t) =>
      t.columns.map((c) => [
        t.name,
        c.name,
        c.type,
        c.nullable ? "허용" : "불가",
        c.default || "—",
        c.note,
      ]),
    ),
    [41, 32, 24, 10, 22, 76],
  );
  add(
    prefix + "_관계",
    prefix + " 제안 FK",
    ["원본", "컬럼", "참조", "참조 컬럼", "삭제/변경"],
    data.relations
      .filter((r) => r.source.startsWith(module + "."))
      .map((r) => [
        r.source,
        r.columns.join(" / "),
        r.target,
        r.target_columns.join(" / "),
        r.on_delete + "/" + r.on_update,
      ]),
    [42, 52, 42, 52, 25],
  );
  add(
    prefix + "_규칙",
    prefix + " 무결성·서비스 정책 제안",
    ["테이블", "상세 계약"],
    tables.flatMap((t) => t.rules.map((rule) => [t.name, rule])),
    [42, 125],
  );
}
wb.recalculate();
const preview = path.join(root, "work/gw-readiness-01/excel");
await fs.mkdir(preview, { recursive: true });
console.log(
  (
    await wb.inspect({
      kind: "match",
      searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?",
      options: { useRegex: true, maxResults: 20 },
      maxChars: 1000,
    })
  ).ndjson,
);
for (const s of sheets) {
  const end = String.fromCharCode(64 + s.heads.length);
  const blob = await wb.render({
    sheetName: s.name,
    range: `A1:${end}${Math.min(11, s.rows.length + 5)}`,
    scale: 1,
    format: "png",
  });
  await fs.writeFile(
    path.join(preview, s.name + ".png"),
    new Uint8Array(await blob.arrayBuffer()),
  );
}
const output = path.join(
  root,
  "docs/modules/gw/review/GW-READY-01_제안DB.xlsx",
);
await (await SpreadsheetFile.exportXlsx(wb)).save(output);
console.log(
  JSON.stringify({
    output,
    sheets: sheets.length,
    newTables: 9,
    extendedTables: 2,
    foreignKeys: data.relations.length,
    productApplied: false,
  }),
);
