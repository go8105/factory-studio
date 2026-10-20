// SPC 화면 공통 (FS-028): API 경로·타입·문구·특성 선택·관리도·히스토그램.
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { EmptyState } from "../shared/components";
import { useSession } from "../app/session";
import { api, ApiError } from "../shared/api";
import { useApiLists, useApiSend } from "../shared/hooks";
export { fieldErrors, moduleOff } from "../shared/hooks";

export const SPC = "/api/v1/spc";

export type Characteristic = {
  id: number;
  code: string;
  itemCode: string;
  itemName: string;
  processCode: string;
  name: string;
  unit: string;
  lsl: string | null;
  usl: string | null;
  target: string | null;
  subgroupSize: number;
  decimals: number;
  isActive: boolean;
  chartType: ChartType;
  defectSource: string | null;
  rules: RuleNo[];
  subgroupCount: number;
  limitVersion: number | null;
  openSignals: number;
};
export type ChartType = "XBAR_R" | "I_MR";
export type RuleNo = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8;
export type ChartKey = "XBAR" | "R" | "I" | "MR";
export type Limit = {
  id: number;
  characteristicId: number;
  version: number;
  effectiveAt: string;
  basisFrom: string;
  basisTo: string;
  basisCount: number;
  xbarCl: string;
  xbarUcl: string;
  xbarLcl: string;
  rCl: string;
  rUcl: string;
  rLcl: string;
  reason: string;
  publishedAt: string;
};
export type SignalMark = {
  id: number;
  subgroupId: number;
  chart: ChartKey;
  rule: RuleNo;
  status: SignalStatus;
};
export type Point = {
  id: number;
  lotNo: string;
  equipmentCode: string;
  measuredAt: string;
  xbar: string;
  r: string;
  status: "valid" | "void";
  limitVersion: number | null;
  signals: SignalMark[];
};
export type ChartData = {
  characteristic: Characteristic;
  limits: Limit[];
  points: Point[];
};
export type SignalStatus = "open" | "resolved" | "void";
export type Cause =
  "MACHINE" | "MATERIAL" | "MAN" | "METHOD" | "MEASUREMENT" | "ENVIRONMENT";
export type Signal = {
  id: number;
  subgroupId: number;
  characteristicId: number;
  characteristicCode: string;
  itemCode: string;
  processCode: string;
  characteristicName: string;
  lotNo: string;
  equipmentCode: string;
  chart: ChartKey;
  rule: RuleNo;
  value: string;
  detectedAt: string;
  status: SignalStatus;
  causeCategory: Cause | null;
  action: string | null;
  resolvedAt: string | null;
  voidedAt: string | null;
  limitVersion: number;
};
export type Subgroup = {
  id: number;
  characteristicId: number;
  lotNo: string;
  itemCode: string;
  processCode: string;
  equipmentCode: string;
  runStartedAt: string;
  runEndedAt: string | null;
  measuredAt: string;
  xbar: string;
  r: string;
  status: "valid" | "void";
  voidReason: string | null;
  voidedAt: string | null;
  source: "SEED" | "MANUAL" | "MES" | "FILE";
  note: string | null;
  measurements: string[];
};
export type Judgement = "CAPABLE" | "MARGINAL" | "INCAPABLE";
export type SpecViolation = {
  id: number;
  subgroupId: number;
  characteristicId: number;
  characteristicCode: string;
  characteristicName: string;
  itemCode: string;
  itemName: string;
  processCode: string;
  unit: string;
  seq: number;
  lotNo: string;
  equipmentCode: string;
  value: string;
  side: "LOW" | "HIGH";
  limitValue: string;
  detectedAt: string;
  voidedAt: string | null;
  status: "open" | "void";
};
export const SIDE_LABEL = { LOW: "하한 미만", HIGH: "상한 초과" } as const;
export type OcapItem = {
  id: number;
  characteristicId: number | null;
  characteristicCode: string | null;
  characteristicName: string | null;
  itemCode: string | null;
  processCode: string | null;
  ruleNo: RuleNo | null;
  seq: number;
  checkText: string;
  causeCategory: Cause | null;
  isActive: boolean;
  checkCount: number;
};
export type OcapResult = "OK" | "NG" | "NA";
export type OcapCheck = {
  id: number;
  signalId: number;
  ocapItemId: number;
  result: OcapResult;
  note: string | null;
  checkedAt: string;
};
export type Checklist = {
  signalId: number;
  status: SignalStatus;
  items: (OcapItem & { check: OcapCheck | null })[];
  missing: number[];
};
export const RESULT_LABEL: Record<OcapResult, string> = {
  OK: "이상 없음",
  NG: "문제 있음",
  NA: "해당 없음",
};
/** 점검 항목의 적용 범위를 한 줄로. 비면 '모든 …'이다. */
export const ocapScope = (i: OcapItem) =>
  `${i.characteristicId ? `${i.itemCode} · ${i.processCode} · ${i.characteristicName}` : "모든 특성"} · ${
    i.ruleNo ? `규칙 ${i.ruleNo}` : "모든 규칙"
  }`;

export const CHART_LABEL = { XBAR: "X̄", R: "R", I: "I", MR: "MR" } as const;
export const CHART_TYPE_LABEL: Record<ChartType, string> = {
  XBAR_R: "X̄-R (부분군 2~10개)",
  I_MR: "I-MR (개별값 1개)",
};
/** Nelson 판정 규칙(DSN-17 Q3). 규칙 1은 끌 수 없다. */
export const RULE_LABEL: Record<RuleNo, string> = {
  1: "규칙 1 · 한계 밖",
  2: "규칙 2 · 한쪽 연속 9점",
  3: "규칙 3 · 연속 6점 증가·감소",
  4: "규칙 4 · 번갈아 14점",
  5: "규칙 5 · 3점 중 2점이 2σ 밖",
  6: "규칙 6 · 5점 중 4점이 1σ 밖",
  7: "규칙 7 · 1σ 안 15점",
  8: "규칙 8 · 1σ 밖 8점",
};
/** S-05 규칙 설명(도움말과 같은 문장). */
export const RULE_TEXT: Record<RuleNo, string> = {
  1: "점이 관리 상한 또는 하한을 벗어났습니다.",
  2: "중심선 한쪽에 연속 9점 찍혔습니다. 평균이 한쪽으로 옮겨 갔을 수 있습니다.",
  3: "연속 6점 증가 또는 감소했습니다. 공정이 한 방향으로 흘러가고 있을 수 있습니다.",
  4: "위아래로 번갈아 14점 찍혔습니다. 서로 다른 두 조건이 섞였을 수 있습니다.",
  5: "연속 3점 중 2점이 같은 쪽 2σ 밖입니다. 큰 치우침이 시작됐을 수 있습니다.",
  6: "연속 5점 중 4점이 같은 쪽 1σ 밖입니다. 평균이 조금씩 옮겨 가고 있을 수 있습니다.",
  7: "연속 15점이 1σ 안에 모였습니다. 산포가 줄었거나 관리 한계가 실제보다 넓습니다.",
  8: "연속 8점이 1σ 밖입니다. 서로 다른 조건의 값이 섞였을 수 있습니다.",
};
export const DEFAULT_RULES: RuleNo[] = [1, 2, 3];
/** 특성이 쓰는 규칙. 고른 것이 없으면 기본 1~3이다(서버와 같은 규칙). */
export const rulesOf = (c: Pick<Characteristic, "rules">) =>
  c.rules.length ? c.rules : DEFAULT_RULES;
export const STATUS_LABEL: Record<SignalStatus, string> = {
  open: "미조치",
  resolved: "조치 완료",
  void: "무효",
};
export const CAUSE_LABEL: Record<Cause, string> = {
  MACHINE: "설비",
  MATERIAL: "자재",
  MAN: "작업자",
  METHOD: "방법",
  MEASUREMENT: "측정",
  ENVIRONMENT: "환경",
};
export const JUDGEMENT_LABEL: Record<Judgement, string> = {
  CAPABLE: "충분",
  MARGINAL: "주의",
  INCAPABLE: "부족",
};
export const JUDGEMENT_TONE: Record<Judgement, "normal" | "warning" | "issue"> =
  { CAPABLE: "normal", MARGINAL: "warning", INCAPABLE: "issue" };

export const num = (v: string | number | null | undefined, digits = 3) =>
  v == null || v === ""
    ? "—"
    : Number(v).toLocaleString("ko-KR", {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      });
export const time = (v: string) =>
  new Date(v).toLocaleString("ko-KR", {
    timeZone: "Asia/Seoul",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });
export const spec = (c: Pick<Characteristic, "lsl" | "usl" | "unit">) =>
  c.lsl && c.usl
    ? `${Number(c.lsl)}~${Number(c.usl)} ${c.unit}`
    : c.usl
      ? `≤ ${Number(c.usl)} ${c.unit}`
      : `≥ ${Number(c.lsl)} ${c.unit}`;
/** 특성의 관리도 두 짝. 위치(X̄·I)와 산포(R·MR)는 같은 칸을 쓰고 이름만 다르다. */
export const chartKeys = (
  c: Pick<Characteristic, "chartType">,
): [ChartKey, ChartKey] =>
  c.chartType === "I_MR" ? ["I", "MR"] : ["XBAR", "R"];
export const label = (c: Characteristic) =>
  `${c.itemCode} · ${c.processCode} · ${c.name}`;

/** datetime-local 값(KST) ↔ ISO. 서버는 시간대가 있는 시각만 받는다. */
export const toIso = (local: string) => `${local}:00+09:00`;
export const toLocal = (iso: string) =>
  new Date(Date.parse(iso) + 9 * 3_600_000).toISOString().slice(0, 16);

export function ModuleOff() {
  return (
    <EmptyState
      reason="SPC를 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다."
      to="/workspace"
      action="내 공간으로"
    />
  );
}

export const useLists = <T extends unknown[]>(paths: string[]) =>
  useApiLists<T>(SPC, paths);
export const useSend = (onDone: () => void) => useApiSend(SPC, onDone);

/** 경로 하나를 불러온다. 경로(조회 조건)나 reload가 바뀌면 다시 부른다. */
export function useGet<T>(path: string | null) {
  const { fail } = useSession();
  const [data, setData] = useState<T>();
  const [error, setError] = useState<unknown>();
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    setError(undefined);
    api<T>(`${SPC}${path}`, { signal: controller.signal })
      .then((r) => !controller.signal.aborted && setData(r.data))
      .catch((e) => {
        if (controller.signal.aborted) return;
        setError(e);
        if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
      });
    return () => controller.abort();
  }, [path, tick]);
  return { data, error, reload: () => setTick((n) => n + 1) };
}

/** 관리도·공정능력·측정 입력이 공유하는 특성 선택. URL ?c=id로 화면 사이에서 유지한다. */
export function useCharacteristic(list: Characteristic[] | undefined) {
  const [params, setParams] = useSearchParams();
  const id = Number(params.get("c")) || list?.[0]?.id;
  const current = list?.find((c) => c.id === id) ?? list?.[0];
  const select = (next: number) => {
    const copy = new URLSearchParams(params);
    copy.set("c", String(next));
    setParams(copy, { replace: true });
  };
  return { current, select, query: current ? `?c=${current.id}` : "" };
}

export function CharacteristicSelect({
  list,
  value,
  onChange,
}: {
  list: Characteristic[];
  value: number | undefined;
  onChange: (id: number) => void;
}) {
  return (
    <label>
      특성
      <select
        value={value ?? ""}
        onChange={(e) => onChange(Number(e.target.value))}
      >
        {list.map((c) => (
          <option key={c.id} value={c.id}>
            {label(c)}
          </option>
        ))}
      </select>
    </label>
  );
}

type Segment = { from: number; to: number; limit: Limit; basis: boolean };

/** 위치(X̄·I) 또는 산포(R·MR) 관리도(reading-chart SVG). 값은 어느 종류든 같은 칸에 들어 있다.
 *  한계선은 버전 구간마다 따로, 버전이 바뀌는 곳은 세로 점선.
 *  점: 정상 ● · 이상 ◆ · 무효 ○(계산 제외). 점마다 초점을 받을 수 있고, 같은 값은 화면 아래 표에도 있다. */
export function ControlChart({
  kind,
  data,
  onSignal,
  height = 190,
}: {
  kind: ChartKey;
  data: ChartData;
  onSignal?: (point: Point) => void;
  height?: number;
}) {
  const { points, limits, characteristic: c } = data;
  const spread = kind === "R" || kind === "MR"; // 산포 관리도는 r 칸을, 위치 관리도는 xbar 칸을 읽는다
  const caption = `${CHART_LABEL[kind]} 관리도`;
  if (!points.length)
    return (
      <figure className="reading-chart" aria-label={caption}>
        <figcaption>{caption}</figcaption>
        <p className="muted">이 기간에 부분군이 없습니다.</p>
      </figure>
    );
  const value = (p: Point) => Number(spread ? p.r : p.xbar);
  const lines = (l: Limit) =>
    spread
      ? { ucl: +l.rUcl, cl: +l.rCl, lcl: +l.rLcl }
      : { ucl: +l.xbarUcl, cl: +l.xbarCl, lcl: +l.xbarLcl };
  const segments: Segment[] = [];
  points.forEach((p, i) => {
    // 판정 버전이 없는 점(게시 전)은 그 점을 기준 구간에 넣어 계산한 버전의 선을 옅게 그린다.
    const at = Date.parse(p.measuredAt);
    const judged = limits.find((l) => l.version === p.limitVersion);
    const limit =
      judged ??
      limits.find(
        (l) => Date.parse(l.basisFrom) <= at && at <= Date.parse(l.basisTo),
      );
    const basis = !judged;
    const last = segments[segments.length - 1];
    if (!limit) return;
    if (
      last &&
      last.limit.version === limit.version &&
      last.basis === basis &&
      last.to === i - 1
    )
      last.to = i;
    else segments.push({ from: i, to: i, limit, basis });
  });
  const W = 760;
  const H = height;
  const pad = { l: 52, r: 92, t: 16, b: 24 };
  const all = [
    ...points.map(value),
    ...segments.flatMap((s) => Object.values(lines(s.limit))),
  ];
  const lo = Math.min(...all);
  const hi = Math.max(...all);
  const span = hi - lo || 1;
  const x = (i: number) =>
    pad.l +
    (points.length === 1 ? 0 : (i / (points.length - 1)) * (W - pad.l - pad.r));
  const y = (v: number) => H - pad.b - ((v - lo) / span) * (H - pad.t - pad.b);
  const digits = c.decimals + 1;
  let lastLotX = -100;
  return (
    <figure className="reading-chart spc-chart" aria-label={caption}>
      <figcaption>
        {caption} ({c.unit})
      </figcaption>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`${caption} — 부분군 ${points.length}개`}
      >
        <line
          className="axis"
          x1={pad.l}
          x2={W - pad.r}
          y1={H - pad.b}
          y2={H - pad.b}
        />
        {segments.map((s) => {
          const l = lines(s.limit);
          const x1 = x(s.from) - 4;
          const x2 = x(s.to) + 4;
          return (
            <g
              key={`${s.limit.version}-${s.from}`}
              className={s.basis ? "spc-basis" : undefined}
            >
              {(s.from > 0 || s.basis) && (
                <>
                  <line
                    className="spc-version"
                    x1={x1}
                    x2={x1}
                    y1={pad.t}
                    y2={H - pad.b}
                  />
                  <text className="tick" x={x1 + 3} y={pad.t - 4}>
                    v{s.limit.version} {s.basis ? "기준 구간" : "적용"}
                  </text>
                </>
              )}
              {(["ucl", "cl", "lcl"] as const).map((k) => (
                <line
                  key={k}
                  className={k === "cl" ? "spc-cl" : "spc-limit"}
                  x1={x1}
                  x2={x2}
                  y1={y(l[k])}
                  y2={y(l[k])}
                />
              ))}
              {s.to === points.length - 1 &&
                (["ucl", "cl", "lcl"] as const).map((k) => (
                  <text
                    key={k}
                    className="tick"
                    x={W - pad.r + 4}
                    y={y(l[k]) + 4}
                  >
                    {k.toUpperCase()} {num(l[k], digits)}
                  </text>
                ))}
            </g>
          );
        })}
        <polyline
          className="series"
          points={points
            .map((p, i) =>
              p.status === "valid" ? `${x(i)},${y(value(p))}` : "",
            )
            .filter(Boolean)
            .join(" ")}
        />
        {points.map((p, i) => {
          const flagged = p.signals.some(
            (s) => s.chart === kind && s.status !== "void",
          );
          const cx = x(i);
          const cy = y(value(p));
          const showLot =
            cx - lastLotX > 70 && (i === 0 || points[i - 1].lotNo !== p.lotNo);
          if (showLot) lastLotX = cx;
          const title = `${time(p.measuredAt)} · ${p.lotNo} · ${p.equipmentCode} · ${CHART_LABEL[kind]} ${num(value(p), digits)}${p.status === "void" ? " · 무효" : ""}${p.signals
            .filter((s) => s.chart === kind)
            .map((s) => ` · ${RULE_LABEL[s.rule]}(${STATUS_LABEL[s.status]})`)
            .join("")}`;
          return (
            <g
              key={p.id}
              tabIndex={flagged && onSignal ? 0 : -1}
              role={flagged && onSignal ? "button" : undefined}
              aria-label={flagged && onSignal ? title : undefined}
              onClick={() => flagged && onSignal?.(p)}
              onKeyDown={(e) => {
                if (
                  flagged &&
                  onSignal &&
                  (e.key === "Enter" || e.key === " ")
                ) {
                  e.preventDefault();
                  onSignal(p);
                }
              }}
              className={flagged && onSignal ? "spc-point-link" : undefined}
            >
              <title>{title}</title>
              {p.status === "void" ? (
                <circle className="spc-void" cx={cx} cy={cy} r={3} />
              ) : flagged ? (
                <rect
                  className="spc-signal"
                  x={cx - 4}
                  y={cy - 4}
                  width={8}
                  height={8}
                  transform={`rotate(45 ${cx} ${cy})`}
                />
              ) : (
                <circle className="marker" cx={cx} cy={cy} r={2.5} />
              )}
              {showLot && (
                <text className="tick" x={cx} y={H - 7} textAnchor="middle">
                  {p.lotNo}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      <p className="chart-tooltip">
        ● 정상 · ◆ 이상 · ○ 무효(계산 제외) · 실선 = 중심선, 점선 = 관리 한계.
        옅은 선은 한계를 계산한 기준 구간(판정하지 않음)입니다. 점에 커서를
        올리면 시각·LOT·설비·값을 볼 수 있습니다.
      </p>
    </figure>
  );
}

/** 작은 X̄ 추이(S-01 카드). 한계선은 최신 버전. */
export function Spark({
  values,
  limit,
}: {
  values: number[];
  limit: Limit | null;
}) {
  if (!values.length) return <p className="muted">부분군 없음</p>;
  const W = 240;
  const H = 48;
  const all = [...values, ...(limit ? [+limit.xbarUcl, +limit.xbarLcl] : [])];
  const lo = Math.min(...all);
  const span = Math.max(...all) - lo || 1;
  const x = (i: number) =>
    values.length === 1 ? 0 : (i / (values.length - 1)) * W;
  const y = (v: number) => H - 4 - ((v - lo) / span) * (H - 8);
  return (
    <svg
      className="spc-spark"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label={`최근 ${values.length}점 X̄ 추이`}
    >
      {limit &&
        [limit.xbarUcl, limit.xbarCl, limit.xbarLcl].map((v, i) => (
          <line
            key={i}
            className={i === 1 ? "spc-cl" : "spc-limit"}
            x1={0}
            x2={W}
            y1={y(+v)}
            y2={y(+v)}
          />
        ))}
      <polyline
        className="series"
        points={values.map((v, i) => `${x(i)},${y(v)}`).join(" ")}
      />
    </svg>
  );
}
