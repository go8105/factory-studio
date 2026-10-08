// M-26 공정 검사 기준 — 공정(·품목)별 초·중·종물 점검 항목 (DSN-12 F52).
// 관리도용 측정은 SPC가 갖는다(D38). 여기 값은 그 공정에서 눈으로 보는 점검이다.
import { useEffect, useState } from "react";
import { api } from "../shared/api";
import { Badge, type Column } from "../shared/components";
import { MasterScreen, type MasterSpec } from "../shared/master";

const METHODS = { RANGE: "수치(상·하한)", PASS_FAIL: "합·부" };
type Lookup = { id: number; code?: string; itemCode?: string; name: string };
type InspectionItem = {
  id: number;
  processId: number;
  itemId: number | null;
  seq: number;
  name: string;
  method: string;
  lowerLimit: string | null;
  upperLimit: string | null;
  unit: string | null;
  isActive: boolean;
};
type Draft = Omit<InspectionItem, "id">;

/** 공정·품목 목록은 화면이 열릴 때 한 번만 읽는다(선택 칸에 이름을 보이려고). */
function useLookups() {
  const [data, setData] = useState<{ processes: Lookup[]; items: Lookup[] }>({
    processes: [],
    items: [],
  });
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      api<Lookup[]>("/api/v1/mes/processes", { signal: controller.signal }),
      api<Lookup[]>("/api/v1/mes/items", { signal: controller.signal }),
    ])
      .then(([processes, items]) =>
        setData({ processes: processes.data, items: items.data }),
      )
      .catch(() => undefined);
    return () => controller.abort();
  }, []);
  return data;
}

export function InspectionItems() {
  const { processes, items } = useLookups();
  const processOptions = Object.fromEntries(
    processes.map((p) => [String(p.id), `${p.code ?? ""} ${p.name}`.trim()]),
  );
  const itemOptions = Object.fromEntries([
    ["", "공정 공통(품목 지정 안 함)"],
    ...items.map((i) => [String(i.id), `${i.itemCode ?? ""} ${i.name}`.trim()]),
  ]);
  const limits = (row: InspectionItem) =>
    row.method === "PASS_FAIL"
      ? "—"
      : `${row.lowerLimit ?? ""} ~ ${row.upperLimit ?? ""} ${row.unit ?? ""}`.trim();
  const columns: Column<InspectionItem>[] = [
    {
      key: "processId",
      label: "공정",
      render: (r) => processes.find((p) => p.id === r.processId)?.name ?? "—",
    },
    {
      key: "itemId",
      label: "품목",
      render: (r) =>
        r.itemId === null
          ? "공정 공통"
          : (items.find((i) => i.id === r.itemId)?.name ?? "—"),
    },
    { key: "seq", label: "순번" },
    { key: "name", label: "점검 항목" },
    {
      key: "method",
      label: "방법",
      render: (r) => METHODS[r.method as keyof typeof METHODS] ?? r.method,
    },
    { key: "lowerLimit", label: "기준", render: limits },
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
  const spec: MasterSpec<InspectionItem, Draft> = {
    id: "M-26",
    title: "공정 검사 기준",
    subtitle: "공정마다 초물·중물·종물에서 볼 항목입니다",
    help: "mes/m-26",
    base: "/api/v1/mes/inspection-items",
    blank: {
      processId: processes[0]?.id ?? 0,
      itemId: null,
      seq: 1,
      name: "",
      method: "RANGE",
      lowerLimit: null,
      upperLimit: null,
      unit: null,
      isActive: true,
    },
    intro: (
      <p>
        품목을 비우면 <b>그 공정 공통</b>입니다. 수치 검사는 상·하한 중 하나와
        단위를 적습니다. 관리도용 측정값은 SPC가 따로 갖습니다.
      </p>
    ),
    columns,
    fields: [
      {
        kind: "select",
        key: "processId",
        label: "공정",
        options: processOptions,
      },
      { kind: "select", key: "itemId", label: "품목", options: itemOptions },
      {
        kind: "number",
        key: "seq",
        label: "순번",
        required: true,
        min: 1,
        max: 99,
      },
      {
        kind: "text",
        key: "name",
        label: "점검 항목",
        required: true,
        maxLength: 100,
      },
      {
        kind: "select",
        key: "method",
        label: "방법",
        options: METHODS,
        note: "합·부 검사는 상·하한과 단위를 쓰지 않습니다.",
      },
      { kind: "text", key: "lowerLimit", label: "하한", maxLength: 16 },
      { kind: "text", key: "upperLimit", label: "상한", maxLength: 16 },
      { kind: "text", key: "unit", label: "단위", maxLength: 10 },
      { kind: "check", key: "isActive", label: "사용" },
    ],
    labels: {
      create: "검사 항목 등록",
      caption: "공정 검사 기준",
      emptyReason:
        "검사 항목이 없습니다. 공정 검사(M-27)에서 쓸 점검 항목을 먼저 만듭니다.",
      editTitle: (row) => `${row.name} 수정`,
      deleted: (row) => `${row.name}을(를) 삭제했습니다.`,
      moduleOff:
        "MES를 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다.",
    },
  };
  return <MasterScreen spec={spec} />;
}
