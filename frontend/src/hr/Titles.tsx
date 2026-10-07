// H-03 직위·직책 — 공통 엔진 (DSN-30 F01). 부서장(isHead)은 휴가 승인자의 근거다.
import { Badge, type Column } from "../shared/components";
import { CODE_PATTERN, MasterScreen, type MasterSpec } from "../shared/master";
export type Title = {
  id: number;
  titleKind: string;
  code: string;
  name: string;
  rankOrder: number;
  isHead: boolean;
  createdAt: string;
};
type Draft = Omit<Title, "id" | "createdAt">;
const KINDS = { GRADE: "직위", DUTY: "직책" };
const columns: Column<Title>[] = [
  {
    key: "titleKind",
    label: "구분",
    render: (r) => KINDS[r.titleKind as keyof typeof KINDS] ?? r.titleKind,
  },
  { key: "code", label: "코드" },
  { key: "name", label: "이름" },
  { key: "rankOrder", label: "서열" },
  {
    key: "isHead",
    label: "부서장",
    render: (r) => (r.isHead ? <Badge>부서장</Badge> : "—"),
  },
];
const spec: MasterSpec<Title, Draft> = {
  id: "H-03",
  title: "직위·직책",
  subtitle: "직위는 등급, 직책은 맡은 자리입니다",
  help: "hr/h-03",
  base: "/api/v1/hr/titles",
  blank: {
    titleKind: "GRADE",
    code: "",
    name: "",
    rankOrder: 1,
    isHead: false,
  },
  columns,
  fields: [
    {
      kind: "select",
      key: "titleKind",
      label: "구분",
      options: KINDS,
      note: "등록 후에는 구분을 바꿀 수 없습니다.",
    },
    {
      kind: "text",
      key: "code",
      label: "코드",
      required: true,
      maxLength: 30,
      pattern: CODE_PATTERN,
      title: "영문 대문자·숫자로 시작하는 1~30자",
      upper: true,
    },
    { kind: "text", key: "name", label: "이름", required: true, maxLength: 60 },
    {
      kind: "number",
      key: "rankOrder",
      label: "서열",
      required: true,
      min: 1,
      note: "숫자가 작을수록 위입니다.",
    },
    {
      kind: "check",
      key: "isHead",
      label: "부서장 (직책에만 — 휴가를 승인합니다)",
    },
  ],
  labels: {
    create: "직위·직책 등록",
    caption: "직위·직책 목록",
    emptyReason: "등록된 직위·직책이 없습니다. 사원 등록에 직위가 필요합니다.",
    editTitle: (row) => `${row.name} 수정`,
    deleted: (row) => `${row.name}을(를) 삭제했습니다.`,
    moduleOff:
      "HR을 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다.",
  },
};
export function Titles() {
  return <MasterScreen spec={spec} />;
}
