// M-17 작업자·근무조 — 공정 실행에 누가 참여했는지 적을 때 고르는 목록 (DSN-12 F08·F39).
// 작업자 코드가 곧 바코드다. 인사 정보는 HR이 갖고, 여기엔 사원 코드만 스냅샷으로 둔다(D79).
import { useEffect, useState } from "react";
import { api } from "../shared/api";
import { Badge, type Column } from "../shared/components";
import { CODE_PATTERN, MasterScreen, type MasterSpec } from "../shared/master";

type Shift = {
  id: number;
  code: string;
  name: string;
  startTime: string;
  endTime: string;
  isActive: boolean;
};
type Worker = {
  id: number;
  code: string;
  name: string;
  shiftId: number | null;
  hrEmployeeCode: string | null;
  isActive: boolean;
};
type ShiftDraft = Omit<Shift, "id">;
type WorkerDraft = Omit<Worker, "id">;

const used = <T extends { isActive: boolean }>(): Column<T> => ({
  key: "isActive",
  label: "사용",
  render: (r) => (
    <Badge tone={r.isActive ? "normal" : "warning"}>
      {r.isActive ? "사용" : "사용 안 함"}
    </Badge>
  ),
});
const shiftSpec: MasterSpec<Shift, ShiftDraft> = {
  id: "M-17",
  title: "근무조",
  subtitle: "작업자를 묶는 교대 단위입니다",
  help: "mes/m-17",
  base: "/api/v1/mes/shifts",
  blank: {
    code: "",
    name: "",
    startTime: "08:00",
    endTime: "20:00",
    isActive: true,
  },
  columns: [
    { key: "code", label: "코드" },
    { key: "name", label: "이름" },
    { key: "startTime", label: "시작" },
    { key: "endTime", label: "종료" },
    used<Shift>(),
  ],
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
    { kind: "time", key: "startTime", label: "시작 시각", required: true },
    { kind: "time", key: "endTime", label: "종료 시각", required: true },
    { kind: "check", key: "isActive", label: "사용" },
  ],
  labels: {
    create: "근무조 등록",
    caption: "근무조",
    emptyReason: "근무조가 없습니다. 교대를 쓰지 않으면 만들지 않아도 됩니다.",
    editTitle: (row) => `${row.name} 수정`,
    deleted: (row) => `${row.name}을(를) 삭제했습니다.`,
    moduleOff:
      "MES를 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다.",
  },
};

/** 근무조 목록은 작업자 화면이 열릴 때 한 번만 읽는다(선택 칸에 이름을 보이려고). */
function useShifts() {
  const [shifts, setShifts] = useState<Shift[]>([]);
  useEffect(() => {
    const controller = new AbortController();
    api<Shift[]>("/api/v1/mes/shifts?limit=200", { signal: controller.signal })
      .then((reply) => setShifts(reply.data))
      .catch(() => undefined);
    return () => controller.abort();
  }, []);
  return shifts;
}

function Workers_({ shifts }: { shifts: Shift[] }) {
  const options = Object.fromEntries([
    ["", "없음"],
    ...shifts.map((s) => [String(s.id), `${s.code} ${s.name}`]),
  ]);
  const spec: MasterSpec<Worker, WorkerDraft> = {
    id: "M-17",
    title: "작업자",
    subtitle: "작업자 코드가 곧 바코드입니다",
    help: "mes/m-17",
    base: "/api/v1/mes/workers",
    blank: {
      code: "",
      name: "",
      shiftId: null,
      hrEmployeeCode: null,
      isActive: true,
    },
    intro: (
      <p>
        인사 정보는 HR이 갖습니다. 여기에는 <b>사원 코드만</b> 적어 두고,
        바뀌어도 자동으로 따라가지 않습니다.
      </p>
    ),
    columns: [
      { key: "code", label: "코드(바코드)" },
      { key: "name", label: "이름" },
      {
        key: "shiftId",
        label: "근무조",
        render: (r) => shifts.find((s) => s.id === r.shiftId)?.name ?? "—",
      },
      {
        key: "hrEmployeeCode",
        label: "HR 사원 코드",
        render: (r) => r.hrEmployeeCode ?? "—",
      },
      used<Worker>(),
    ],
    fields: [
      {
        kind: "text",
        key: "code",
        label: "코드(바코드)",
        required: true,
        maxLength: 30,
        pattern: CODE_PATTERN,
        title: "영문 대문자·숫자로 시작하는 1~30자",
        upper: true,
      },
      {
        kind: "text",
        key: "name",
        label: "이름",
        required: true,
        maxLength: 100,
      },
      { kind: "select", key: "shiftId", label: "근무조", options },
      {
        kind: "text",
        key: "hrEmployeeCode",
        label: "HR 사원 코드 (선택)",
        maxLength: 30,
        pattern: CODE_PATTERN,
        title: "HR 사원 화면(H-05)의 사원 코드",
        upper: true,
      },
      { kind: "check", key: "isActive", label: "사용" },
    ],
    labels: {
      create: "작업자 등록",
      caption: "작업자",
      emptyReason:
        "작업자가 없습니다. 공정 실행에 참여자를 적으려면 먼저 만듭니다.",
      editTitle: (row) => `${row.name} 수정`,
      deleted: (row) => `${row.name}을(를) 삭제했습니다.`,
      moduleOff:
        "MES를 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다.",
    },
  };
  return <MasterScreen spec={spec} />;
}

const TABS = { worker: "작업자", shift: "근무조" };

export function Workers() {
  const [tab, setTab] = useState<keyof typeof TABS>("worker");
  const shifts = useShifts();
  return (
    <div className="page-fill">
      <nav className="filter-bar" aria-label="작업자·근무조 구분">
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
      {tab === "worker" ? (
        <Workers_ shifts={shifts} />
      ) : (
        <MasterScreen spec={shiftSpec} />
      )}
    </div>
  );
}
