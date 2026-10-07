// H-02 부서 — 공통 엔진에 선언만 넘긴다 (DSN-30 F01)
import { Badge, type Column } from "../shared/components";
import { CODE_PATTERN, MasterScreen, type MasterSpec } from "../shared/master";
export type Department = {
  id: number;
  code: string;
  name: string;
  parentId: number | null;
  displayOrder: number;
  isActive: boolean;
  createdAt: string;
};
type Draft = Omit<Department, "id" | "createdAt">;
const columns: Column<Department>[] = [
  { key: "code", label: "부서 코드" },
  { key: "name", label: "부서명" },
  { key: "displayOrder", label: "표시 순서" },
  {
    key: "isActive",
    label: "사용",
    render: (r) => (
      <Badge tone={r.isActive ? "normal" : "warning"}>
        {r.isActive ? "사용" : "사용 안 함"}
      </Badge>
    ),
  },
];
const spec: MasterSpec<Department, Draft> = {
  id: "H-02",
  title: "부서",
  subtitle: "부서 코드는 다른 솔루션이 가져다 쓰는 원천입니다",
  help: "hr/h-02",
  base: "/api/v1/hr/departments",
  blank: {
    code: "",
    name: "",
    parentId: null,
    displayOrder: 1,
    isActive: true,
  },
  columns,
  filter: { label: "사용 중인 부서만", query: "active=true" },
  fields: [
    {
      kind: "text",
      key: "code",
      label: "부서 코드",
      required: true,
      maxLength: 30,
      pattern: CODE_PATTERN,
      title: "영문 대문자·숫자로 시작하는 1~30자",
      upper: true,
    },
    {
      kind: "text",
      key: "name",
      label: "부서명",
      required: true,
      maxLength: 100,
    },
    { kind: "check", key: "isActive", label: "사용 (끄면 새 입력에서 제외)" },
  ],
  labels: {
    create: "부서 등록",
    caption: "부서 목록",
    emptyReason:
      "등록된 부서가 없습니다. 사원을 등록하려면 부서가 먼저 필요합니다.",
    editTitle: (row) => `${row.name} 수정`,
    deleted: (row) => `${row.name} 부서를 삭제했습니다.`,
    moduleOff:
      "HR을 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다.",
  },
};
export function Departments() {
  return <MasterScreen spec={spec} />;
}
