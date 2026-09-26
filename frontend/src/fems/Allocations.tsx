// F-03 설비별 배분 — 저장된 배분 결과 조회 + 계산 근거 패널 (FS-018c)
import { useEffect, useState, type FormEvent } from "react";
import { useSession } from "../app/session";
import { api, ApiError } from "../shared/api";
import {
  Badge,
  DataTable,
  EmptyState,
  ErrorNotice,
  Loading,
  PageTitle,
  type Column,
} from "../shared/components";
import type { EnergySource } from "./EnergySources";
export type Allocation = {
  id: number;
  periodStart: string;
  periodEnd: string;
  timezone: string;
  equipmentId: number;
  equipmentCode: string;
  equipmentName: string;
  channelCode: string;
  channelName: string;
  energySourceCode: string;
  quantity: string;
  unit: string;
  methodKey: string;
  methodVersion: number;
  inputRevision: number;
  quality: "valid" | "estimated" | "invalid";
  basis: Record<string, unknown>;
  isLatest: boolean;
};
export type SummaryRow = {
  equipmentId: number;
  equipmentCode: string;
  equipmentName: string;
  energySourceCode: string;
  unit: string;
  quantity: string;
  days: number;
  estimatedDays: number;
};
type Equipment = { id: number; equipmentCode: string; name: string };
type Filters = {
  from: string;
  to: string;
  equipmentId: string;
  energySourceId: string;
  methodKey: string;
  includeSuperseded: boolean;
};
const LIMIT = 50;
export const METHODS: Record<string, string> = {
  DIRECT_METER: "전용 계량기 직접 귀속",
  RUNTIME_SHARE: "가동시간 비례",
};
export const BASIS_LABELS: Record<string, string> = {
  summed_hours: "합산 시간",
  missing_hours: "결측 시간",
  runtime_hours: "가동 시간",
  common_unallocated: "공용 미배분량",
  active_equipment_count: "가동 설비 수",
};
const QUALITY = {
  valid: ["정상", "normal"],
  estimated: ["추정", "warning"],
  invalid: ["무효", "issue"],
} as const;
const NONE: Filters = {
  from: "",
  to: "",
  equipmentId: "",
  energySourceId: "",
  methodKey: "",
  includeSuperseded: false,
};
function formatDay(iso: string, timeZone: string) {
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone,
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(iso));
}
function query(f: Filters, offset: number) {
  const params = new URLSearchParams({
    offset: String(offset),
    limit: String(LIMIT),
  });
  for (const key of [
    "from",
    "to",
    "equipmentId",
    "energySourceId",
    "methodKey",
  ] as const)
    if (f[key]) params.set(key, f[key]);
  if (f.includeSuperseded) params.set("includeSuperseded", "true");
  return params.toString();
}
// 공통 규격 6-4 "계산 근거 패널": 접었다 펴는 패널에 배분 방법과 근거를 담는다.
export function BasisPanel({ row }: { row: Allocation }) {
  return (
    <details className="basis-panel">
      <summary>근거</summary>
      <dl>
        <div>
          <dt>배분 방법</dt>
          <dd>
            {METHODS[row.methodKey] ?? row.methodKey} · v{row.methodVersion}
          </dd>
        </div>
        <div>
          <dt>입력 버전</dt>
          <dd>{row.inputRevision}</dd>
        </div>
        {Object.entries(row.basis).map(([key, value]) => (
          <div key={key}>
            <dt>{BASIS_LABELS[key] ?? key}</dt>
            <dd>{String(value)}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}
// 단위가 다르면 표를 나눈다. 전력 kWh와 용수 m3를 한 합계에 넣지 않는다(AGENTS §3).
export function AllocationSummary({ rows }: { rows: SummaryRow[] }) {
  const units = [...new Set(rows.map((r) => r.unit))];
  if (!units.length) return null;
  return (
    <section className="summary-grid" aria-label="설비별 합계">
      {units.map((unit) => (
        <div key={unit} className="panel">
          <h2>설비별 합계 · {unit}</h2>
          <table>
            <caption>현재 결과 기준, 무효 제외</caption>
            <thead>
              <tr>
                <th scope="col">설비</th>
                <th scope="col" className="num">
                  합계
                </th>
                <th scope="col">일수</th>
              </tr>
            </thead>
            <tbody>
              {rows
                .filter((r) => r.unit === unit)
                .map((r) => (
                  <tr key={`${r.equipmentId}-${unit}`}>
                    <td>
                      {r.equipmentCode} {r.equipmentName}
                    </td>
                    <td className="num">
                      {Number(r.quantity).toLocaleString()}
                    </td>
                    <td>
                      {r.days}
                      {r.estimatedDays > 0 && (
                        <>
                          {" "}
                          <Badge tone="warning">추정 {r.estimatedDays}일</Badge>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      ))}
    </section>
  );
}
export function Allocations() {
  const { fail } = useSession();
  const [equipments, setEquipments] = useState<Equipment[]>([]);
  const [sources, setSources] = useState<EnergySource[]>([]);
  const [draft, setDraft] = useState<Filters>(NONE);
  const [applied, setApplied] = useState<Filters>(NONE);
  const [offset, setOffset] = useState(0);
  const [rows, setRows] = useState<Allocation[]>();
  const [summary, setSummary] = useState<SummaryRow[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<unknown>();
  const [reload, setReload] = useState(0);
  const handle = (e: unknown) => {
    setError(e);
    if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
  };
  useEffect(() => {
    api<Equipment[]>("/api/v1/fems/equipments?limit=200")
      .then((r) => setEquipments(r.data))
      .catch(handle);
    api<EnergySource[]>("/api/v1/fems/energy-sources?limit=200")
      .then((r) => setSources(r.data))
      .catch(handle);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    setError(undefined);
    setRows(undefined);
    api<Allocation[]>(`/api/v1/fems/allocations?${query(applied, offset)}`, {
      signal: controller.signal,
    })
      .then((r) => {
        const extra = r as {
          range?: { from: string; to: string } | null;
          summary?: SummaryRow[];
        };
        setRows(r.data);
        setTotal(r.page?.total ?? 0);
        setSummary(extra.summary ?? []);
        if (extra.range && !applied.from)
          setDraft((d) => ({ ...d, ...extra.range }));
      })
      .catch((e) => {
        if (!controller.signal.aborted) handle(e);
      });
    return () => controller.abort();
  }, [applied, offset, reload]);
  function submit(event: FormEvent) {
    event.preventDefault();
    setOffset(0);
    setApplied(draft);
  }
  if (
    error instanceof ApiError &&
    error.error.details?.reason === "MODULE_DISABLED"
  )
    return (
      <EmptyState
        reason="FEMS를 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다."
        to="/workspace"
        action="내 공간으로"
      />
    );
  const fieldErrors =
    error instanceof ApiError && error.error.code === "VALIDATION_FAILED"
      ? ((error.error.details?.fields ?? {}) as Record<string, string>)
      : {};
  const columns: Column<Allocation>[] = [
    {
      key: "periodStart",
      label: "날짜",
      render: (r) => formatDay(r.periodStart, r.timezone),
    },
    {
      key: "equipmentCode",
      label: "설비",
      render: (r) => `${r.equipmentCode} ${r.equipmentName}`,
    },
    { key: "channelName", label: "채널" },
    {
      key: "quantity",
      label: "배분량",
      render: (r) => Number(r.quantity).toLocaleString(),
    },
    { key: "unit", label: "단위" },
    {
      key: "methodKey",
      label: "방법",
      render: (r) => METHODS[r.methodKey] ?? r.methodKey,
    },
    {
      key: "quality",
      label: "품질",
      render: (r) => (
        <Badge tone={QUALITY[r.quality][1]}>{QUALITY[r.quality][0]}</Badge>
      ),
    },
    ...(applied.includeSuperseded
      ? [
          {
            key: "isLatest" as const,
            label: "결과",
            render: (r: Allocation) => (
              <Badge tone={r.isLatest ? "normal" : "warning"}>
                {r.isLatest ? "현재" : "이전"}
              </Badge>
            ),
          },
        ]
      : []),
    { key: "id", label: "근거", render: (r) => <BasisPanel row={r} /> },
  ];
  const set = (key: keyof Filters) => (value: string) =>
    setDraft((d) => ({ ...d, [key]: value }));
  return (
    <>
      <PageTitle
        id="F-03"
        title="설비별 배분"
        subtitle="계측값을 설비 단위로 배분한 결과와 그 근거"
        help="fems/f-03"
      />
      <form
        className="filter-bar"
        aria-label="설비별 배분 조회 조건"
        onSubmit={submit}
      >
        <label>
          시작일
          <input
            type="date"
            value={draft.from}
            aria-invalid={!!fieldErrors.from}
            onChange={(e) => set("from")(e.target.value)}
          />
        </label>
        <label>
          종료일
          <input
            type="date"
            value={draft.to}
            aria-invalid={!!fieldErrors.to}
            onChange={(e) => set("to")(e.target.value)}
          />
        </label>
        <label>
          설비
          <select
            value={draft.equipmentId}
            onChange={(e) => set("equipmentId")(e.target.value)}
          >
            <option value="">전체</option>
            {equipments.map((q) => (
              <option key={q.id} value={q.id}>
                {q.equipmentCode} {q.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          에너지원
          <select
            value={draft.energySourceId}
            onChange={(e) => set("energySourceId")(e.target.value)}
          >
            <option value="">전체</option>
            {sources.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          배분 방법
          <select
            value={draft.methodKey}
            onChange={(e) => set("methodKey")(e.target.value)}
          >
            <option value="">전체</option>
            {Object.entries(METHODS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="inline-check">
          <input
            type="checkbox"
            checked={draft.includeSuperseded}
            onChange={(e) =>
              setDraft((d) => ({ ...d, includeSuperseded: e.target.checked }))
            }
          />
          이전 산정 결과 포함
        </label>
        <button type="submit">조회</button>
      </form>
      <ErrorNotice error={error} retry={() => setReload((n) => n + 1)} />
      {!rows ? (
        !error && <Loading delay={300} />
      ) : (
        <>
          <AllocationSummary rows={summary} />
          <DataTable
            rows={rows}
            columns={columns}
            caption="배분 결과"
            offset={offset}
            total={total}
            limit={LIMIT}
            onPage={setOffset}
            empty={
              <EmptyState
                reason="조건에 맞는 배분 결과가 없습니다. 기간을 넓히거나 필터를 해제해 보세요."
                to="/fems/readings"
                action="계측값 보기"
              />
            }
          />
        </>
      )}
    </>
  );
}
