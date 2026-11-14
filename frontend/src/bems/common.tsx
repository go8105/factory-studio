// BEMS 화면 공통 (FS-025): API 경로·타입·문구·1시간 진행 버튼·선 그래프.
import { useEffect, useState } from "react";
import { EmptyState, ErrorNotice } from "../shared/components";
import { useSession } from "../app/session";
import { api, ApiError } from "../shared/api";
import { useApiLists, useApiSend } from "../shared/hooks";
export { fieldErrors, moduleOff } from "../shared/hooks";

export const BEMS = "/api/v1/bems";

export type Metric = "TEMP" | "HUMIDITY" | "CO2" | "PM25" | "LUX" | "OCCUPANCY";
/** 환경 경보 규칙은 지표 3종 그대로다(DSN-16은 센서만 6종으로 늘렸다). */
export type AlarmMetric = "TEMP" | "HUMIDITY" | "CO2";
export const ALARM_METRICS: AlarmMetric[] = ["TEMP", "HUMIDITY", "CO2"];
export const METRICS: Metric[] = [
  "TEMP",
  "HUMIDITY",
  "CO2",
  "PM25",
  "LUX",
  "OCCUPANCY",
];
export type Mode = "COOL" | "HEAT" | "FAN";
export type State = "OFF" | Mode;
export type SetpointKind = "COOL_TEMP" | "HEAT_TEMP" | "CO2_MAX";
export type Setpoints = Record<SetpointKind, string>;
export type Zone = {
  id: number;
  code: string;
  name: string;
  kind: "OFFICE" | "PRODUCTION" | "UTILITY";
  floorAreaM2: string | null;
  isActive: boolean;
  buildingId: number | null;
  floorLabel: string | null;
  departmentCode: string | null;
};
export type Building = {
  id: number;
  code: string;
  name: string;
  floors: number;
  grossAreaM2: string;
  isActive: boolean;
};
export type LightingCircuit = {
  id: number;
  zoneId: number;
  code: string;
  name: string;
  meterId: number | null;
  ratedKw: string;
  state: "ON" | "OFF";
  controlSource: "SCHEDULE" | "MANUAL";
  stateChangedAt: string | null;
  isActive: boolean;
};
export type CircuitDetail = LightingCircuit & {
  commands: Command[];
  schedule: Slot[];
};
export type Departments = {
  hrEnabled: boolean;
  rows: { code: string; name: string }[];
};
export type Meter = {
  id: number;
  zoneId: number;
  code: string;
  name: string;
  usage: "LIGHTING" | "HVAC" | "OFFICE" | "OTHER";
  unit: string;
  isActive: boolean;
};
export type Sensor = {
  id: number;
  zoneId: number;
  code: string;
  metric: Metric;
  unit: string;
  isActive: boolean;
};
export type HvacUnit = {
  id: number;
  zoneId: number;
  code: string;
  name: string;
  meterId: number | null;
  ratedKw: string;
  state: State;
  controlSource: "SCHEDULE" | "MANUAL";
  stateChangedAt: string | null;
  isActive: boolean;
  curtailPriority: number;
};
export type DayKind = "WEEKDAY" | "WEEKEND" | "HOLIDAY";
export type Slot = {
  id?: number;
  dayKind: DayKind;
  startHour: number;
  endHour: number;
  mode: Mode | "ON";
};
export type Command = {
  id: number;
  zoneId: number;
  hvacUnitId: number | null;
  hvacCode: string | null;
  lightingCircuitId: number | null;
  lightingCode: string | null;
  demandPlanId: number | null;
  command: "POWER_ON" | "POWER_OFF" | "SET_MODE" | "SET_SETPOINT";
  mode: Mode | null;
  setpointKind: SetpointKind | null;
  value: string | null;
  source: "MANUAL" | "SCHEDULE" | "PEAK";
  requestedAt: string;
  result: "APPLIED" | "REJECTED";
  rejectReason: string | null;
  note: string | null;
};
export type Overview = HvacUnit & {
  setpoints: Setpoints;
  environment: Partial<Record<Metric, string>>;
  lastPower: string | null;
};
export type UnitDetail = HvacUnit & {
  setpoints: Setpoints;
  commands: Command[];
  schedule: Slot[];
};
export type Alarm = {
  id: number;
  alarmRuleId: number;
  sensorId: number;
  status: "raised" | "acknowledged" | "cleared";
  raisedAt: string;
  peakValue: string;
  acknowledgedAt: string | null;
  ackNote: string | null;
  clearedAt: string | null;
  zoneId: number;
  zoneCode: string;
  zoneName: string;
  metric: AlarmMetric;
  comparator: "HIGH" | "LOW";
  threshold: string;
  durationHours: number;
  severity: "WARNING" | "CRITICAL";
};
export type ComfortStandard = {
  id: number;
  zoneKind: Zone["kind"];
  metric: Metric;
  low: string | null;
  high: string | null;
  occupiedOnly: boolean;
};
export type ComfortRow = {
  zoneId: number;
  zoneCode: string;
  zoneName: string;
  zoneKind: Zone["kind"];
  metric: Metric;
  unit: string;
  low: string | null;
  high: string | null;
  occupiedOnly: boolean;
  hours: number;
  insideHours: number;
  ratio: string | null;
  reason: "NO_SCHEDULE" | "NO_READINGS" | null;
};
export type PeakAlarm = {
  ruleCode: string;
  ruleName: string;
  alarmKind: string;
  threshold: string;
  unit: string;
  peakValue: string;
  status: string;
  raisedAt: string;
  alarmRef: string;
  planId: number | null;
  overKw: string | null;
};
export type PlanStep = {
  id: number;
  seq: number;
  hvacUnitId: number | null;
  hvacCode: string | null;
  hvacName: string | null;
  curtailPriority: number | null;
  lightingCircuitId: number | null;
  action: "RAISE_SETPOINT" | "SET_FAN" | "POWER_OFF";
  deltaValue: string | null;
  expectedKw: string;
  commandId: number | null;
  restoreCommandId: number | null;
};
export type DemandPlan = {
  id: number;
  planNo: string;
  femsAlarmRef: string;
  proposedAt: string;
  targetReductionKw: string;
  status: "PROPOSED" | "APPROVED" | "EXECUTED" | "RESTORED" | "REJECTED";
  decidedAt: string | null;
  executedAt: string | null;
  restoredAt: string | null;
  decisionNote: string | null;
  expectedKw?: string;
  steps?: PlanStep[];
  alarmOpen?: boolean | null;
};
export const PLAN_STATUS: Record<DemandPlan["status"], string> = {
  PROPOSED: "제안",
  APPROVED: "승인",
  EXECUTED: "실행",
  RESTORED: "복귀",
  REJECTED: "반려",
};
export const ACTION_LABEL: Record<PlanStep["action"], string> = {
  RAISE_SETPOINT: "냉방 설정 상향",
  SET_FAN: "송풍 전환",
  POWER_OFF: "정지",
};
export const actionText = (s: Pick<PlanStep, "action" | "deltaValue">) =>
  s.action === "RAISE_SETPOINT"
    ? `${ACTION_LABEL[s.action]} +${num(s.deltaValue)}℃`
    : ACTION_LABEL[s.action];

export type EquipmentRule = {
  id: number;
  code: string;
  condition: "COMMAND_REJECTED" | "LONG_RUN";
  hvacUnitId: number | null;
  threshold: string;
  severity: "WARNING" | "CRITICAL";
  isActive: boolean;
};
export type EquipmentAlarm = {
  id: number;
  ruleId: number;
  hvacUnitId: number;
  status: "raised" | "acknowledged" | "cleared";
  raisedAt: string;
  acknowledgedAt: string | null;
  clearedAt: string | null;
  ruleCode: string;
  condition: EquipmentRule["condition"];
  threshold: string;
  severity: EquipmentRule["severity"];
  hvacCode: string;
  hvacName: string;
  zoneId: number;
};
export const CONDITION_LABEL: Record<EquipmentRule["condition"], string> = {
  COMMAND_REJECTED: "명령 연속 거부",
  LONG_RUN: "연속 운전",
};
export const CONDITION_UNIT: Record<EquipmentRule["condition"], string> = {
  COMMAND_REJECTED: "회",
  LONG_RUN: "시간",
};
export const COMFORT_REASON: Record<string, string> = {
  NO_SCHEDULE: "운전 스케줄이 없어 근무 시간을 알 수 없습니다",
  NO_READINGS: "이 기간에 관측이 없습니다",
};

export type Rule = {
  id: number;
  zoneId: number;
  metric: AlarmMetric;
  comparator: "HIGH" | "LOW";
  threshold: string;
  durationHours: number;
  severity: "WARNING" | "CRITICAL";
  isActive: boolean;
};
export type BreakdownRow = {
  period: string;
  site: string;
  manufacturing: string;
  common: string;
  commonByUsage: Partial<Record<Meter["usage"], string>>;
  residual: string;
  mismatch: boolean;
  missingHours: number;
};
export type Clock = { next: string; limit: string; canAdvance: boolean };
export type AdvanceResult = {
  from: string;
  to: string;
  hours: number;
  readings: number;
  switches: number;
  raised: number;
  cleared: number;
};

export const METRIC_LABEL: Record<Metric, string> = {
  TEMP: "실내 온도",
  HUMIDITY: "습도",
  CO2: "CO₂",
  PM25: "미세먼지",
  LUX: "조도",
  OCCUPANCY: "재실 인원",
};
export const UNIT: Record<Metric, string> = {
  TEMP: "℃",
  HUMIDITY: "%",
  CO2: "ppm",
  PM25: "㎍/㎥",
  LUX: "lx",
  OCCUPANCY: "명",
};
export const STATE_LABEL: Record<State, string> = {
  OFF: "정지",
  COOL: "냉방",
  HEAT: "난방",
  FAN: "송풍",
};
/** 스케줄·명령 표시용. 조명 회로는 켜짐(ON)뿐이라 공조 모드와 섞지 않는다. */
export const SLOT_LABEL: Record<Mode | "ON", string> = {
  ...{ COOL: "냉방", HEAT: "난방", FAN: "송풍" },
  ON: "켜짐",
};
export const LIGHT_LABEL = { ON: "켜짐", OFF: "꺼짐" } as const;
export const SOURCE_LABEL = {
  SCHEDULE: "스케줄",
  MANUAL: "수동",
  PEAK: "피크 감축",
} as const;
export const KIND_LABEL: Record<Zone["kind"], string> = {
  OFFICE: "사무동",
  PRODUCTION: "생산동",
  UTILITY: "유틸리티",
};
export const USAGE_LABEL: Record<Meter["usage"], string> = {
  LIGHTING: "조명",
  HVAC: "공조",
  OFFICE: "사무동 콘센트",
  OTHER: "기타",
};
export const SETPOINT_LABEL: Record<SetpointKind, string> = {
  COOL_TEMP: "냉방 설정",
  HEAT_TEMP: "난방 설정",
  CO2_MAX: "CO₂ 상한",
};
/** simulation.py SETPOINT_RANGE와 같다 — 입력 안내용. 판정은 서버가 한다. */
export const SETPOINT_RANGE: Record<SetpointKind, [number, number, string]> = {
  COOL_TEMP: [20, 30, "℃"],
  HEAT_TEMP: [16, 24, "℃"],
  CO2_MAX: [600, 2000, "ppm"],
};
export const COMMAND_LABEL: Record<Command["command"], string> = {
  POWER_ON: "전원 켜기",
  POWER_OFF: "전원 끄기",
  SET_MODE: "모드 변경",
  SET_SETPOINT: "설정값 변경",
};
export const REJECT_LABEL: Record<string, string> = {
  OUT_OF_RANGE: "허용 범위 밖",
  BAND_TOO_NARROW: "냉방·난방 간격 2℃ 미만",
  UNIT_INACTIVE: "사용 안 함 공조기",
  ALREADY_ON: "이미 켜져 있음",
  ALREADY_OFF: "이미 꺼져 있음",
  SAME_STATE: "이미 같은 모드",
};
export const DAY_LABEL: Record<DayKind, string> = {
  WEEKDAY: "평일",
  WEEKEND: "주말",
  HOLIDAY: "휴일",
};
/** 스케줄 요일 구분 순서. 서버 _scheduled_mode와 같다(휴일 > 토·일 > 평일). */
export const DAY_KINDS: DayKind[] = ["WEEKDAY", "WEEKEND", "HOLIDAY"];
export const SEVERITY_LABEL = { WARNING: "경고", CRITICAL: "위험" } as const;
export const STATUS_LABEL: Record<Alarm["status"], string> = {
  raised: "확인 대기",
  acknowledged: "확인됨",
  cleared: "해제됨",
};

export const num = (v: string | number | null | undefined, digits = 1) =>
  v == null || v === ""
    ? "—"
    : Number(v).toLocaleString("ko-KR", { maximumFractionDigits: digits });
export const time = (v: string) =>
  new Date(v).toLocaleString("ko-KR", {
    timeZone: "Asia/Seoul",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });
export const hourLabel = (v: string) =>
  new Date(v).toLocaleTimeString("ko-KR", {
    timeZone: "Asia/Seoul",
    hour: "2-digit",
    hourCycle: "h23",
  });
export const commandText = (c: Command) =>
  c.command === "SET_MODE"
    ? `${COMMAND_LABEL[c.command]} · ${STATE_LABEL[c.mode ?? "FAN"]}`
    : c.command === "SET_SETPOINT" && c.setpointKind
      ? `${SETPOINT_LABEL[c.setpointKind]} ${num(c.value)}${SETPOINT_RANGE[c.setpointKind][2]}`
      : COMMAND_LABEL[c.command];
export const ruleText = (
  r: Pick<Rule, "metric" | "comparator" | "threshold" | "durationHours">,
) =>
  `${r.comparator === "HIGH" ? ">" : "<"} ${num(r.threshold)} ${UNIT[r.metric]} · ${r.durationHours}시간`;

export function ModuleOff() {
  return (
    <EmptyState
      reason="BEMS를 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다."
      to="/workspace"
      action="내 공간으로"
    />
  );
}

export const useLists = <T extends unknown[]>(paths: string[]) =>
  useApiLists<T>(BEMS, paths);
export const useSend = (onDone: () => void) => useApiSend(BEMS, onDone);

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
    api<T>(`${BEMS}${path}`, { signal: controller.signal })
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

/** 1시간 진행(TX-B2). B-01·B-04 두 곳에서 같은 API를 쓴다. 결과는 role=status로 알린다. */
export function AdvanceControl({
  onDone,
  choices = [1],
}: {
  onDone: () => void;
  choices?: number[];
}) {
  const [clock, setClock] = useState<Clock>();
  const [tick, setTick] = useState(0);
  const [hours, setHours] = useState(choices[0]);
  const [result, setResult] = useState<AdvanceResult>();
  const { send, pending, error } = useSend(() => {
    setTick((n) => n + 1);
    onDone();
  });
  useEffect(() => {
    void api<Clock>(`${BEMS}/simulation/clock`)
      .then((r) => setClock(r.data))
      .catch(() => setClock(undefined));
  }, [tick]);
  async function advance() {
    const r = await send<AdvanceResult>("/simulation/advance", "POST", {
      hours,
    });
    if (r) setResult(r);
  }
  return (
    <div className="bems-advance">
      <span className="muted">시뮬레이션 {clock ? time(clock.next) : "—"}</span>
      {choices.length > 1 && (
        <select
          aria-label="진행 시간"
          value={hours}
          onChange={(e) => setHours(Number(e.target.value))}
        >
          {choices.map((h) => (
            <option key={h} value={h}>
              {h}시간
            </option>
          ))}
        </select>
      )}
      <button
        type="button"
        disabled={pending || !clock?.canAdvance}
        aria-busy={pending}
        title={
          clock && !clock.canAdvance
            ? "업무 기준일 다음 날 00:00까지 진행했습니다. 세대를 초기화하면 다시 진행할 수 있습니다."
            : undefined
        }
        onClick={() => void advance()}
      >
        {choices.length > 1 ? "진행" : "1시간 진행"}
      </button>
      {clock && !clock.canAdvance && (
        <small className="muted">진행 한도(업무 기준일 다음 날 00:00)</small>
      )}
      <p role="status" className="bems-advance-result">
        {result &&
          `${time(result.from)}부터 ${result.hours}시간 진행 · 관측 ${result.readings}건 생성 · 스케줄 전환 ${result.switches} · 경보 발생 ${result.raised} · 해제 ${result.cleared}`}
      </p>
      <ErrorNotice error={error} />
    </div>
  );
}

export type Series = {
  label: string;
  points: { at: string; value: number; simulated?: boolean }[];
};
/** 시간축 선 그래프(FEMS F-02 reading-chart 방식). 기준선(설정값·상한)은 점선. 값은 표로도 읽는다. */
export function LineChart({
  caption,
  unit,
  series,
  references = [],
}: {
  caption: string;
  unit: string;
  series: Series;
  references?: { label: string; value: number }[];
}) {
  const pts = series.points;
  if (!pts.length)
    return (
      <figure className="reading-chart" aria-label={caption}>
        <figcaption>{caption}</figcaption>
        <p className="muted">이 기간에 관측이 없습니다.</p>
      </figure>
    );
  const W = 720;
  const H = 170;
  const pad = { l: 44, r: 12, t: 12, b: 22 };
  const values = [
    ...pts.map((p) => p.value),
    ...references.map((r) => r.value),
  ];
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const span = hi - lo || 1;
  const x = (i: number) =>
    pad.l +
    (pts.length === 1 ? 0 : (i / (pts.length - 1)) * (W - pad.l - pad.r));
  const y = (v: number) => H - pad.b - ((v - lo) / span) * (H - pad.t - pad.b);
  const step = Math.max(1, Math.ceil(pts.length / 8));
  return (
    <figure className="reading-chart" aria-label={caption}>
      <figcaption>
        {caption} ({unit})
      </figcaption>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`${caption} 선 그래프`}
      >
        <line
          className="axis"
          x1={pad.l}
          x2={W - pad.r}
          y1={H - pad.b}
          y2={H - pad.b}
        />
        <text className="tick" x={pad.l - 6} y={y(hi) + 4} textAnchor="end">
          {num(hi)}
        </text>
        <text className="tick" x={pad.l - 6} y={y(lo)} textAnchor="end">
          {num(lo)}
        </text>
        {references.map((r) => (
          <g key={r.label}>
            <line
              className="grid"
              x1={pad.l}
              x2={W - pad.r}
              y1={y(r.value)}
              y2={y(r.value)}
            />
            <text
              className="tick"
              x={W - pad.r}
              y={y(r.value) - 4}
              textAnchor="end"
            >
              {r.label} {num(r.value)}
            </text>
          </g>
        ))}
        <polyline
          className="series"
          points={pts.map((p, i) => `${x(i)},${y(p.value)}`).join(" ")}
        />
        {pts.map((p, i) => (
          <g key={p.at}>
            <title>{`${time(p.at)} · ${num(p.value)} ${unit}${p.simulated ? " · 진행으로 생성" : ""}`}</title>
            {p.simulated ? (
              <rect
                className="marker"
                x={x(i) - 3}
                y={y(p.value) - 3}
                width={6}
                height={6}
              />
            ) : (
              <circle className="marker" cx={x(i)} cy={y(p.value)} r={2.5} />
            )}
            {i % step === 0 && (
              <text className="tick" x={x(i)} y={H - 6} textAnchor="middle">
                {hourLabel(p.at)}
              </text>
            )}
          </g>
        ))}
      </svg>
      <p className="chart-tooltip">
        실선 = 관측{references.length ? " · 점선 = 설정값·상한" : ""} · 동그라미
        = 시드 관측, 네모 = 진행으로 생성. 점에 커서를 올리면 시각별 값을 볼 수
        있습니다.
      </p>
    </figure>
  );
}

/** 제조·공용·잔여 누적 막대(B-01 최근 7일, B-02 기간 합계). */
export function ShareBars({
  rows,
  caption,
}: {
  rows: BreakdownRow[];
  caption: string;
}) {
  const W = 720;
  const H = 170;
  const pad = { l: 44, r: 12, t: 12, b: 22 };
  const max = Math.max(...rows.map((r) => Number(r.site)), 1);
  const slot = (W - pad.l - pad.r) / Math.max(rows.length, 1);
  const bar = Math.min(40, slot * 0.6);
  const h = (v: number) => (Math.max(v, 0) / max) * (H - pad.t - pad.b);
  const parts = [
    ["manufacturing", "제조", "var(--accent)"],
    ["common", "공용", "var(--accent-soft)"],
    ["residual", "잔여", "var(--border)"],
  ] as const;
  return (
    <figure className="reading-chart" aria-label={caption}>
      <figcaption>{caption} (kWh)</figcaption>
      {rows.length ? (
        <svg
          viewBox={`0 0 ${W} ${H}`}
          role="img"
          aria-label={`${caption} 누적 막대 그래프`}
        >
          <line
            className="axis"
            x1={pad.l}
            x2={W - pad.r}
            y1={H - pad.b}
            y2={H - pad.b}
          />
          <text className="tick" x={pad.l - 6} y={pad.t + 4} textAnchor="end">
            {num(max, 0)}
          </text>
          {rows.map((r, i) => {
            let base = H - pad.b;
            const x = pad.l + slot * i + (slot - bar) / 2;
            return (
              <g key={r.period}>
                <title>{`${r.period} · 제조 ${num(r.manufacturing, 0)} · 공용 ${num(r.common, 0)} · 잔여 ${num(r.residual, 0)}`}</title>
                {parts.map(([k, , fill]) => {
                  const height = h(Number(r[k]));
                  base -= height;
                  return (
                    <rect
                      key={k}
                      x={x}
                      y={base}
                      width={bar}
                      height={height}
                      fill={fill}
                    />
                  );
                })}
                <text
                  className="tick"
                  x={x + bar / 2}
                  y={H - 6}
                  textAnchor="middle"
                >
                  {r.period.length > 7 ? r.period.slice(5) : r.period}
                </text>
              </g>
            );
          })}
        </svg>
      ) : (
        <p className="muted">이 기간의 사업장 전력이 없습니다.</p>
      )}
      <p className="chart-tooltip">
        아래부터 {parts.map(([, label]) => label).join(" · ")}. 잔여가 음수인
        날은 막대에 그리지 않고 표에 불일치로 표시합니다.
      </p>
    </figure>
  );
}

/** 스케줄 모드(서버 _scheduled_mode와 같은 규칙: KST 요일·시각, 없으면 OFF). */
function scheduledMode(slots: Slot[], at: number): string {
  const d = new Date(at);
  const hour = Number(
    d.toLocaleString("en-US", {
      timeZone: "Asia/Seoul",
      hour: "numeric",
      hourCycle: "h23",
    }),
  );
  const wd = d.toLocaleString("en-US", {
    timeZone: "Asia/Seoul",
    weekday: "short",
  });
  const kind = wd === "Sat" || wd === "Sun" ? "WEEKEND" : "WEEKDAY";
  return (
    slots.find(
      (s) => s.dayKind === kind && s.startHour <= hour && hour < s.endHour,
    )?.mode ?? "OFF"
  );
}
/** 수동 운전이 스케줄로 돌아가는 다음 경계 시각. 7일 안에 없으면 null. */
export function nextBoundary(slots: Slot[], from: string): string | null {
  const start = Date.parse(from);
  for (let h = 0; h < 24 * 7; h++) {
    const at = start + h * 3_600_000;
    if (scheduledMode(slots, at) !== scheduledMode(slots, at - 3_600_000))
      return new Date(at).toISOString();
  }
  return null;
}
