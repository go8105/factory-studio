// H-04 근무 형태 — 공통 엔진 (DSN-30 F11). 일 근태 자동 생성의 기준이다.
import { type Column } from "../shared/components";
import { CODE_PATTERN, MasterScreen, type MasterSpec } from "../shared/master";
export type WorkPattern = {
  id: number;
  code: string;
  name: string;
  patternKind: string;
  startTime: string;
  scheduledMinutes: number;
  breakMinutes: number;
  worksWeekend: boolean;
  createdAt: string;
};
type Draft = Omit<WorkPattern, "id" | "createdAt">;
const KINDS = { DAY: "일근", TWO_SHIFT: "2교대", THREE_SHIFT: "3교대" };
const hours = (minutes: number) =>
  `${Math.floor(minutes / 60)}시간 ${minutes % 60}분`;
const columns: Column<WorkPattern>[] = [
  { key: "code", label: "코드" },
  { key: "name", label: "이름" },
  {
    key: "patternKind",
    label: "유형",
    render: (r) => KINDS[r.patternKind as keyof typeof KINDS] ?? r.patternKind,
  },
  { key: "startTime", label: "시작" },
  {
    key: "scheduledMinutes",
    label: "소정 근로",
    render: (r) => hours(r.scheduledMinutes),
  },
  { key: "breakMinutes", label: "휴게", render: (r) => hours(r.breakMinutes) },
  {
    key: "worksWeekend",
    label: "주말",
    render: (r) => (r.worksWeekend ? "근무" : "휴무"),
  },
];
const spec: MasterSpec<WorkPattern, Draft> = {
  id: "H-04",
  title: "근무 형태",
  subtitle: "일 근태를 자동으로 만들 때의 기준입니다",
  help: "hr/h-04",
  base: "/api/v1/hr/work-patterns",
  blank: {
    code: "",
    name: "",
    patternKind: "DAY",
    startTime: "09:00:00",
    scheduledMinutes: 480,
    breakMinutes: 60,
    worksWeekend: false,
  },
  columns,
  fields: [
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
    { kind: "select", key: "patternKind", label: "유형", options: KINDS },
    { kind: "time", key: "startTime", label: "시작 시각", required: true },
    {
      kind: "number",
      key: "scheduledMinutes",
      label: "소정 근로(분)",
      required: true,
      min: 1,
      max: 720,
      note: "480분 = 8시간",
    },
    {
      kind: "number",
      key: "breakMinutes",
      label: "휴게(분)",
      required: true,
      min: 0,
      max: 480,
    },
    { kind: "check", key: "worksWeekend", label: "주말에도 근무" },
  ],
  labels: {
    create: "근무 형태 등록",
    caption: "근무 형태 목록",
    emptyReason: "등록된 근무 형태가 없습니다. 사원 등록에 필요합니다.",
    editTitle: (row) => `${row.name} 수정`,
    deleted: (row) => `${row.name} 근무 형태를 삭제했습니다.`,
    moduleOff:
      "HR을 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다.",
  },
};
export function WorkPatterns() {
  return <MasterScreen spec={spec} />;
}
