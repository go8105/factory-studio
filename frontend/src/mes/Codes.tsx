// M-16 불량·사유 코드 — 실적의 불량과 비가동·폐기 사유를 코드로 적는다 (DSN-12 F06·F07).
// 자유 입력 대신 코드를 쓰면 집계가 된다. 쓰던 코드는 지우지 말고 '사용 안 함'으로 바꾼다.
import { useState } from "react";
import { Badge, type Column } from "../shared/components";
import { CODE_PATTERN, MasterScreen, type MasterSpec } from "../shared/master";

export const DEFECT_CATEGORIES = {
  APPEARANCE: "외관",
  DIMENSION: "치수",
  FUNCTION: "기능",
  OTHER: "기타",
};
export const REASON_CATEGORIES = {
  DOWNTIME: "비가동",
  ADJUST: "비계획 입출고",
  SCRAP: "폐기",
  REWORK: "재작업",
};
export type DefectCode = {
  id: number;
  code: string;
  name: string;
  category: string;
  isActive: boolean;
};
type ReasonCode = DefectCode & { planned: boolean };
type DefectDraft = Omit<DefectCode, "id">;
type ReasonDraft = Omit<ReasonCode, "id">;

const active = <T extends { isActive: boolean }>(): Column<T> => ({
  key: "isActive",
  label: "사용",
  render: (r) => (
    <Badge tone={r.isActive ? "normal" : "warning"}>
      {r.isActive ? "사용" : "사용 안 함"}
    </Badge>
  ),
});
const CODE_FIELD = {
  kind: "text" as const,
  key: "code" as const,
  label: "코드",
  required: true,
  maxLength: 30,
  pattern: CODE_PATTERN,
  title: "영문 대문자·숫자로 시작하는 1~30자",
  upper: true,
};

const defectSpec: MasterSpec<DefectCode, DefectDraft> = {
  id: "M-16",
  title: "불량 코드",
  subtitle: "실적의 불량을 코드로 적습니다",
  help: "mes/m-16",
  base: "/api/v1/mes/defect-codes",
  blank: { code: "", name: "", category: "APPEARANCE", isActive: true },
  intro: (
    <p>
      실적 확정(M-07)에서 고르는 목록입니다. 공정마다 보일 코드는 공정(M-13)에서
      정합니다.
    </p>
  ),
  columns: [
    { key: "code", label: "코드" },
    { key: "name", label: "이름" },
    {
      key: "category",
      label: "구분",
      render: (r) =>
        DEFECT_CATEGORIES[r.category as keyof typeof DEFECT_CATEGORIES] ??
        r.category,
    },
    active<DefectCode>(),
  ],
  fields: [
    CODE_FIELD,
    {
      kind: "text",
      key: "name",
      label: "이름",
      required: true,
      maxLength: 100,
    },
    {
      kind: "select",
      key: "category",
      label: "구분",
      options: DEFECT_CATEGORIES,
    },
    { kind: "check", key: "isActive", label: "사용" },
  ],
  labels: {
    create: "불량 코드 등록",
    caption: "불량 코드",
    emptyReason: "불량 코드가 없습니다. 실적에 불량을 적으려면 먼저 만듭니다.",
    editTitle: (row) => `${row.name} 수정`,
    deleted: (row) => `${row.name}을(를) 삭제했습니다.`,
    moduleOff:
      "MES를 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다.",
  },
};

const reasonSpec: MasterSpec<ReasonCode, ReasonDraft> = {
  id: "M-16",
  title: "사유 코드",
  subtitle: "비가동·비계획 입출고·폐기·재작업의 이유를 코드로 적습니다",
  help: "mes/m-16",
  base: "/api/v1/mes/reason-codes",
  blank: {
    category: "DOWNTIME",
    code: "",
    name: "",
    planned: false,
    isActive: true,
  },
  intro: (
    <p>
      <b>계획된 정지</b>는 비가동 사유에만 표시합니다 — 예방보전처럼 미리 잡아
      둔 정지는 가동률에서 다르게 봅니다.
    </p>
  ),
  columns: [
    {
      key: "category",
      label: "구분",
      render: (r) =>
        REASON_CATEGORIES[r.category as keyof typeof REASON_CATEGORIES] ??
        r.category,
    },
    { key: "code", label: "코드" },
    { key: "name", label: "이름" },
    {
      key: "planned",
      label: "계획",
      render: (r) => (r.planned ? <Badge>계획된 정지</Badge> : "—"),
    },
    active<ReasonCode>(),
  ],
  fields: [
    {
      kind: "select",
      key: "category",
      label: "구분",
      options: REASON_CATEGORIES,
      note: "등록 후에는 구분을 바꿀 수 없습니다.",
    },
    CODE_FIELD,
    {
      kind: "text",
      key: "name",
      label: "이름",
      required: true,
      maxLength: 100,
    },
    { kind: "check", key: "planned", label: "계획된 정지 (비가동에만)" },
    { kind: "check", key: "isActive", label: "사용" },
  ],
  labels: {
    create: "사유 코드 등록",
    caption: "사유 코드",
    emptyReason: "사유 코드가 없습니다. 비가동·폐기를 적으려면 먼저 만듭니다.",
    editTitle: (row) => `${row.name} 수정`,
    deleted: (row) => `${row.name}을(를) 삭제했습니다.`,
    moduleOff:
      "MES를 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다.",
  },
};

const TABS = { defect: "불량 코드", reason: "사유 코드" };

export function Codes() {
  const [tab, setTab] = useState<keyof typeof TABS>("defect");
  return (
    <div className="page-fill">
      <nav className="filter-bar" aria-label="코드 구분">
        {Object.entries(TABS).map(([key, label]) => (
          <button
            key={key}
            type="button"
            className={tab === key ? "" : "secondary"}
            aria-pressed={tab === key}
            onClick={() => setTab(key as keyof typeof TABS)}
          >
            {label}
          </button>
        ))}
      </nav>
      {/* key를 주어 탭을 바꾸면 화면을 새로 띄운다 — 같은 컴포넌트라 목록이 그대로 남는다. */}
      {tab === "defect" ? (
        <MasterScreen key="defect" spec={defectSpec} />
      ) : (
        <MasterScreen key="reason" spec={reasonSpec} />
      )}
    </div>
  );
}
