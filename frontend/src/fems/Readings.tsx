// F-02 계측 조회 — FEMS 조회 화면 패턴의 기준 구현 (FS-018b)
// 필터는 초안(draft)과 적용값(applied)을 나눈다. 조회 버튼을 눌러야 요청한다.
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
export type Reading = {
  id: number;
  observedAt: string;
  periodStart: string | null;
  timezone: string;
  meterCode: string;
  channelId: number;
  channelCode: string;
  channelName: string;
  energySourceCode: string;
  value: string | null;
  unit: string;
  quality: "valid" | "estimated" | "reset" | "invalid";
};
type Meter = {
  id: number;
  meterCode: string;
  name: string;
  channels: { id: number; channelCode: string; name: string }[];
};
type Filters = {
  from: string;
  to: string;
  meterId: string;
  channelId: string;
  energySourceId: string;
  quality: string;
};
const TABLE_LIMIT = 50;
const CHART_LIMIT = 200;
const QUALITY = {
  valid: ["정상", "normal"],
  estimated: ["추정", "warning"],
  reset: ["리셋", "warning"],
  invalid: ["결측", "issue"],
} as const;
const NONE: Filters = {
  from: "",
  to: "",
  meterId: "",
  channelId: "",
  energySourceId: "",
  quality: "",
};
export function formatAt(iso: string, timeZone: string) {
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone,
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).format(new Date(iso));
}
function query(f: Filters, offset: number, limit: number) {
  const params = new URLSearchParams({
    offset: String(offset),
    limit: String(limit),
  });
  const keys: [keyof Filters, string][] = [
    ["from", "from"],
    ["to", "to"],
    ["meterId", "meterId"],
    ["channelId", "channelId"],
    ["energySourceId", "energySourceId"],
    ["quality", "quality"],
  ];
  for (const [key, name] of keys) if (f[key]) params.set(name, f[key]);
  return params.toString();
}
export function Readings() {
  const { fail } = useSession();
  const [meters, setMeters] = useState<Meter[]>([]);
  const [sources, setSources] = useState<EnergySource[]>([]);
  const [draft, setDraft] = useState<Filters>(NONE);
  const [applied, setApplied] = useState<Filters>(NONE);
  const [offset, setOffset] = useState(0);
  const [view, setView] = useState<"table" | "chart">("table");
  const [rows, setRows] = useState<Reading[]>();
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<unknown>();
  const [reload, setReload] = useState(0);
  const handle = (e: unknown) => {
    setError(e);
    if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
  };
  useEffect(() => {
    api<Meter[]>("/api/v1/fems/meters")
      .then((r) => setMeters(r.data))
      .catch(handle);
    api<EnergySource[]>("/api/v1/fems/energy-sources?limit=200")
      .then((r) => setSources(r.data))
      .catch(handle);
  }, []);
  const limit = view === "chart" ? CHART_LIMIT : TABLE_LIMIT;
  useEffect(() => {
    const controller = new AbortController();
    setError(undefined);
    setRows(undefined);
    api<Reading[]>(`/api/v1/fems/readings?${query(applied, offset, limit)}`, {
      signal: controller.signal,
    })
      .then((r) => {
        // 보기·페이지를 바꾼 뒤 늦게 도착한 이전 응답은 버린다.
        if (controller.signal.aborted) return;
        setRows(r.data);
        setTotal(r.page?.total ?? 0);
        // 기간을 비워 조회하면 서버가 최근 7일을 정한다. 입력 칸에 그 기간을 보여준다.
        const range = (r as { range?: { from: string; to: string } | null })
          .range;
        // 적용값은 비워 둔 채 두어 같은 조회를 다시 요청하지 않는다.
        if (range && !applied.from) setDraft((d) => ({ ...d, ...range }));
      })
      .catch((e) => {
        if (!controller.signal.aborted) handle(e);
      });
    return () => controller.abort();
  }, [applied, offset, limit, reload]);
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
  const channels = meters
    .filter((m) => !draft.meterId || String(m.id) === draft.meterId)
    .flatMap((m) => m.channels);
  const columns: Column<Reading>[] = [
    {
      key: "observedAt",
      label: "관측 시각",
      render: (r) => formatAt(r.observedAt, r.timezone),
    },
    { key: "meterCode", label: "계측기" },
    { key: "channelName", label: "채널" },
    { key: "energySourceCode", label: "에너지원" },
    {
      key: "value",
      label: "값",
      render: (r) => (r.value === null ? "결측" : r.value),
    },
    { key: "unit", label: "단위" },
    {
      key: "quality",
      label: "품질",
      render: (r) => (
        <Badge tone={QUALITY[r.quality][1]}>{QUALITY[r.quality][0]}</Badge>
      ),
    },
  ];
  const set = (key: keyof Filters) => (value: string) =>
    setDraft((d) => ({
      ...d,
      [key]: value,
      ...(key === "meterId" ? { channelId: "" } : {}),
    }));
  // 보기 전환은 결과 수·CSV와 같은 줄에 둔다(표·그래프 공통).
  const viewTabs = (
    <div className="tabs" role="group" aria-label="보기 방식">
      {(
        [
          ["table", "표"],
          ["chart", "선 그래프"],
        ] as const
      ).map(([key, label]) => (
        <button
          key={key}
          type="button"
          aria-pressed={view === key}
          onClick={() => {
            setOffset(0);
            setView(key);
          }}
        >
          {label}
        </button>
      ))}
    </div>
  );
  // 조회 목록 기준 화면(UI-02): 제목 → 조건 → 보기·결과 수 → 남은 높이를 쓰는 결과 → 페이지 이동
  return (
    <div className="page-fill">
      <PageTitle
        id="F-02"
        title="계측 조회"
        subtitle="채널별 원시 계측값 · 1시간 해상도 고정"
        help="fems/f-02"
      />
      <form
        className="filter-bar"
        aria-label="계측 조회 조건"
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
          계측기
          <select
            value={draft.meterId}
            onChange={(e) => set("meterId")(e.target.value)}
          >
            <option value="">전체</option>
            {meters.map((m) => (
              <option key={m.id} value={m.id}>
                {m.meterCode} {m.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          채널
          <select
            value={draft.channelId}
            onChange={(e) => set("channelId")(e.target.value)}
          >
            <option value="">전체</option>
            {channels.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
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
          품질
          <select
            value={draft.quality}
            onChange={(e) => set("quality")(e.target.value)}
          >
            <option value="">전체</option>
            {Object.entries(QUALITY).map(([value, [label]]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <button type="submit">조회</button>
      </form>
      <ErrorNotice error={error} retry={() => setReload((n) => n + 1)} />
      {view === "chart" ? (
        <section className="fill">
          <div className="table-toolbar">
            <div className="table-toolbar-lead">
              {viewTabs}
              {rows && (
                <p>
                  총 <strong>{total.toLocaleString()}</strong>건 · 앞{" "}
                  {CHART_LIMIT}건까지 그립니다
                </p>
              )}
            </div>
          </div>
          {!rows ? (
            !error && <Loading delay={300} />
          ) : (
            <ReadingChart rows={rows} channelSelected={!!applied.channelId} />
          )}
        </section>
      ) : !rows ? (
        <>
          {viewTabs}
          {!error && <Loading delay={300} />}
        </>
      ) : (
        <DataTable
          leading={viewTabs}
          rows={rows}
          columns={columns}
          caption="계측값"
          offset={offset}
          total={total}
          limit={TABLE_LIMIT}
          onPage={setOffset}
          empty={
            <EmptyState
              reason="조건에 맞는 계측값이 없습니다. 기간을 넓히거나 필터를 해제해 보세요."
              to="/fems/energy-sources"
              action="에너지원 기준정보 보기"
            />
          }
        />
      )}
    </div>
  );
}
// 채널 1개의 선 그래프. 결측은 0으로 그리지 않고 선을 끊는다(FS-005g 5.2).
export function ReadingChart({
  rows,
  channelSelected,
}: {
  rows: Reading[];
  channelSelected: boolean;
}) {
  const [hover, setHover] = useState<number>();
  if (!channelSelected)
    return (
      <p className="empty">
        채널을 하나 고르고 조회하면 선 그래프를 볼 수 있습니다. 단위가 다른
        채널을 한 축에 그리지 않습니다.
      </p>
    );
  if (!rows.length)
    return <p className="empty">조건에 맞는 계측값이 없습니다.</p>;
  const W = 720;
  const H = 240;
  const pad = { l: 56, r: 16, t: 16, b: 32 };
  const values = rows.map((r) => (r.value === null ? null : Number(r.value)));
  const max = Math.max(...values.map((v) => v ?? 0), 1);
  const x = (i: number) =>
    pad.l +
    (rows.length === 1 ? 0 : (i / (rows.length - 1)) * (W - pad.l - pad.r));
  const y = (v: number) => H - pad.b - (v / max) * (H - pad.t - pad.b);
  let d = "";
  values.forEach((v, i) => {
    if (v === null) return;
    d += `${i === 0 || values[i - 1] === null ? "M" : "L"}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
  });
  const missing = values.filter((v) => v === null).length;
  const first = rows[0];
  const last = rows[rows.length - 1];
  const point = hover === undefined ? undefined : rows[hover];
  return (
    <figure className="reading-chart">
      <figcaption>
        {first.channelName} ({first.unit}) ·{" "}
        {formatAt(first.observedAt, first.timezone)} ~{" "}
        {formatAt(last.observedAt, last.timezone)}
        {missing > 0 && ` · 결측 ${missing}건은 선을 끊어 표시`}
      </figcaption>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`${first.channelName} 계측값 선 그래프`}
        onMouseLeave={() => setHover(undefined)}
        onMouseMove={(e) => {
          const box = e.currentTarget.getBoundingClientRect();
          const px = ((e.clientX - box.left) / box.width) * W;
          const i = Math.round(
            ((px - pad.l) / (W - pad.l - pad.r)) * (rows.length - 1),
          );
          setHover(Math.min(rows.length - 1, Math.max(0, i)));
        }}
      >
        <line className="axis" x1={pad.l} x2={W - pad.r} y1={y(0)} y2={y(0)} />
        <line
          className="grid"
          x1={pad.l}
          x2={W - pad.r}
          y1={y(max)}
          y2={y(max)}
        />
        <text className="tick" x={pad.l - 8} y={y(0)} textAnchor="end">
          0
        </text>
        <text className="tick" x={pad.l - 8} y={y(max) + 4} textAnchor="end">
          {max.toLocaleString()}
        </text>
        <path className="series" d={d} />
        {point && (
          <g>
            <line
              className="crosshair"
              x1={x(hover!)}
              x2={x(hover!)}
              y1={pad.t}
              y2={H - pad.b}
            />
            {point.value !== null && (
              <circle
                className="marker"
                cx={x(hover!)}
                cy={y(Number(point.value))}
                r={4}
              />
            )}
          </g>
        )}
      </svg>
      <p className="chart-tooltip" aria-live="polite">
        {point
          ? `${formatAt(point.observedAt, point.timezone)} · ${
              point.value === null ? "결측" : `${point.value} ${point.unit}`
            }`
          : "그래프 위에 커서를 올리면 시각별 값을 볼 수 있습니다."}
      </p>
    </figure>
  );
}
