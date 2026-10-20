// C-09 고장 코드 — 작업지시에서 고르는 증상·원인·조치 코드 (UI-03 S 패턴, DSN-21 F24).
// 같은 코드라도 구분이 다르면 따로 쓴다("NOISE"가 증상이면서 조치일 수 있다).
import { Badge, type Column } from "../shared/components";
import { CODE_PATTERN, MasterScreen, type MasterSpec } from "../shared/master";
import {
  CAUSE_LABEL,
  CMMS,
  CODE_KIND_LABEL,
  type Cause,
  type CodeKind,
  type FailureCode,
} from "./common";

type Draft = {
  kind: CodeKind;
  code: string;
  name: string;
  causeCategory: Cause | "";
  isActive: boolean;
};

const columns: Column<FailureCode>[] = [
  {
    key: "kind",
    label: "구분",
    render: (r) => CODE_KIND_LABEL[r.kind],
  },
  { key: "code", label: "코드" },
  { key: "name", label: "이름" },
  {
    key: "causeCategory",
    label: "원인 분류",
    render: (r) =>
      r.causeCategory ? (
        CAUSE_LABEL[r.causeCategory]
      ) : (
        <span className="muted">—</span>
      ),
  },
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

const spec: MasterSpec<FailureCode, Draft> = {
  id: "C-09",
  title: "고장 코드",
  subtitle: "작업지시에서 고르는 증상·원인·조치 코드입니다",
  help: "cmms/c-09",
  base: `${CMMS}/failure-codes`,
  blank: {
    kind: "SYMPTOM",
    code: "",
    name: "",
    causeCategory: "",
    isActive: true,
  },
  intro: (
    <p role="note" className="muted">
      <strong>원인 코드에만 원인 분류를 답니다.</strong> 증상은 "무엇이
      보였는가", 원인은 "왜 그랬는가", 조치는 "무엇을 했는가"입니다. 분류는 보전
      지표에서 고장을 묶는 기준이 되므로 원인에만 필요합니다.
    </p>
  ),
  columns,
  fields: [
    {
      kind: "select",
      key: "kind",
      label: "구분",
      options: CODE_KIND_LABEL,
      note: "등록 뒤에는 바꿀 수 없습니다. 구분이 다르면 같은 코드를 또 쓸 수 있습니다.",
    },
    {
      kind: "text",
      key: "code",
      label: "코드",
      required: true,
      maxLength: 20,
      pattern: CODE_PATTERN,
      title: "영문 대문자로 시작하는 2~20자",
      upper: true,
    },
    {
      kind: "text",
      key: "name",
      label: "이름",
      required: true,
      maxLength: 100,
    },
    {
      kind: "select",
      key: "causeCategory",
      label: "원인 분류",
      options: { "": "없음", ...CAUSE_LABEL },
      note: "원인 코드는 반드시 고르고, 증상·조치는 비워 둡니다.",
    },
    { kind: "check", key: "isActive", label: "사용" },
  ],
  labels: {
    create: "고장 코드 등록",
    caption: "고장 코드",
    emptyReason:
      "고장 코드가 없습니다. 없어도 작업지시를 쓸 수 있지만, 코드가 있어야 고장을 묶어 볼 수 있습니다.",
    editTitle: (row) => `${CODE_KIND_LABEL[row.kind]} ${row.code} 수정`,
    deleted: (row) => `${row.code}을(를) 삭제했습니다.`,
    moduleOff:
      "CMMS를 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다.",
  },
};

export function FailureCodes() {
  return <MasterScreen spec={spec} />;
}
