// F-18 에너지 경보 — 규칙과 발생 이력 (DSN-15 F31)
// 상시 감시가 아니다. "지금 점검"을 누를 때 규칙을 한 번 본다.
import { useEffect, useState } from "react";
import { useSession } from "../app/session";
import { api, ApiError } from "../shared/api";
import {
  Badge,
  ErrorNotice,
  Field,
  Loading,
  PageTitle,
} from "../shared/components";
import { fieldErrors } from "../shared/hooks";

type Kind = "THRESHOLD" | "PEAK" | "IDLE_USAGE";
const KIND_LABEL: Record<Kind, string> = {
  THRESHOLD: "시간 사용량 임계",
  PEAK: "계약전력 대비 피크",
  IDLE_USAGE: "비가동 시간 사용",
};
const STATUS_LABEL = { OPEN: "발생", ACK: "확인", CLEARED: "해제" } as const;

type Rule = {
  id: number;
  code: string;
  name: string;
  alarmKind: Kind;
  meterChannelId: number | null;
  threshold: string;
  unit: string;
  isActive: boolean;
};
type Alarm = {
  id: number;
  ruleCode: string;
  ruleName: string;
  alarmKind: Kind;
  threshold: string;
  unit: string;
  channelCode: string | null;
  equipmentCode: string | null;
  raisedAt: string;
  peakValue: string;
  status: keyof typeof STATUS_LABEL;
};
type Meter = {
  id: number;
  meterCode: string;
  channels: { id: number; channelCode: string; name: string }[];
};

const EMPTY = {
  code: "",
  name: "",
  alarmKind: "THRESHOLD" as Kind,
  meterChannelId: "",
  threshold: "",
  unit: "kWh",
};
const num = (v: string) =>
  Number(v).toLocaleString("ko-KR", { maximumFractionDigits: 3 });
const when = (iso: string) =>
  new Date(iso).toLocaleString("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });

export function Alarms() {
  const { session, fail } = useSession();
  const [rules, setRules] = useState<Rule[]>();
  const [alarms, setAlarms] = useState<Alarm[]>();
  const [meters, setMeters] = useState<Meter[]>([]);
  const [draft, setDraft] = useState(EMPTY);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<unknown>();
  const [done, setDone] = useState<string>();
  const [pending, setPending] = useState(false);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setError(undefined);
    Promise.all([
      api<Rule[]>("/api/v1/fems/alarm-rules", { signal: controller.signal }),
      api<Alarm[]>("/api/v1/fems/alarms", { signal: controller.signal }),
      api<Meter[]>("/api/v1/fems/meters", { signal: controller.signal }),
    ])
      .then(([r, a, m]) => {
        if (controller.signal.aborted) return;
        setRules(r.data);
        setAlarms(a.data);
        setMeters(m.data);
      })
      .catch((e) => {
        if (controller.signal.aborted) return;
        setError(e);
        if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
      });
    return () => controller.abort();
  }, [reload]);

  async function send<T>(path: string, body?: unknown): Promise<T | undefined> {
    if (!session?.csrfToken) return undefined;
    setPending(true);
    setError(undefined);
    try {
      const r = await api<T>(`/api/v1/fems${path}`, {
        method: "POST",
        body,
        csrf: session.csrfToken,
        key: `al-${Date.now()}`,
      });
      setReload((n) => n + 1);
      return r.data;
    } catch (e) {
      setError(e);
      return undefined;
    } finally {
      setPending(false);
    }
  }

  async function evaluate() {
    const r = await send<{ raised: string[]; skipped: string[] }>(
      "/alarms/evaluate",
      {},
    );
    if (r)
      setDone(
        r.raised.length
          ? `${r.raised.length}건이 올라왔습니다 — ${r.raised.join(", ")}`
          : "걸린 규칙이 없습니다." +
              (r.skipped.length ? ` (건너뜀 ${r.skipped.length}건)` : ""),
      );
  }

  async function addRule() {
    const saved = await send<Rule>("/alarm-rules", {
      code: draft.code.trim().toUpperCase(),
      name: draft.name.trim(),
      alarmKind: draft.alarmKind,
      meterChannelId: draft.meterChannelId
        ? Number(draft.meterChannelId)
        : null,
      threshold: draft.threshold.trim(),
      unit: draft.unit.trim(),
    });
    if (saved) {
      setDraft(EMPTY);
      setAdding(false);
      setDone(`규칙 ${saved.code}을(를) 만들었습니다.`);
    }
  }

  const errors = fieldErrors(error);
  const channels = meters.flatMap((m) =>
    m.channels.map((c) => ({ ...c, meterCode: m.meterCode })),
  );
  const open = (alarms ?? []).filter((a) => a.status !== "CLEARED");

  return (
    <>
      <PageTitle
        id="F-18"
        title="에너지 경보"
        subtitle="임계·피크·비가동 사용 규칙과 발생 이력"
        help="fems/f-18"
        actions={
          <>
            <button
              type="button"
              disabled={pending}
              onClick={() => void evaluate()}
            >
              지금 점검
            </button>
            <button
              type="button"
              className="secondary"
              aria-pressed={adding}
              onClick={() => setAdding((v) => !v)}
            >
              규칙 추가
            </button>
          </>
        }
      />
      <ErrorNotice error={Object.keys(errors).length ? undefined : error} />
      {done && <p role="status">{done}</p>}
      <p className="muted" role="note">
        <strong>상시 감시가 아닙니다.</strong> 지금 점검을 누를 때 규칙을 한 번
        봅니다. 규칙당 진행 중인 경보는 하나이고, 해제한 뒤 다시 걸리면 새
        경보가 올라옵니다.
      </p>
      {adding && (
        <div className="section-block">
          <div className="field-row">
            <Field
              label="규칙 코드"
              value={draft.code}
              required
              error={errors.code}
              onChange={(e) => setDraft({ ...draft, code: e.target.value })}
            />
            <Field
              label="이름"
              value={draft.name}
              required
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
            />
            <label>
              종류
              <select
                value={draft.alarmKind}
                onChange={(e) =>
                  setDraft({ ...draft, alarmKind: e.target.value as Kind })
                }
              >
                {(Object.keys(KIND_LABEL) as Kind[]).map((k) => (
                  <option key={k} value={k}>
                    {KIND_LABEL[k]}
                  </option>
                ))}
              </select>
            </label>
            <label>
              계측 채널
              <select
                value={draft.meterChannelId}
                onChange={(e) =>
                  setDraft({ ...draft, meterChannelId: e.target.value })
                }
              >
                <option value="">선택</option>
                {channels.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.meterCode} · {c.channelCode}
                  </option>
                ))}
              </select>
            </label>
            <Field
              label="임계값"
              inputMode="decimal"
              value={draft.threshold}
              required
              error={errors.threshold}
              onChange={(e) =>
                setDraft({ ...draft, threshold: e.target.value })
              }
            />
            <Field
              label="단위"
              value={draft.unit}
              required
              onChange={(e) => setDraft({ ...draft, unit: e.target.value })}
            />
            <button
              type="button"
              disabled={
                pending || !draft.code.trim() || !draft.threshold.trim()
              }
              onClick={() => void addRule()}
            >
              규칙 저장
            </button>
          </div>
          <p className="muted">
            {draft.alarmKind === "PEAK"
              ? "피크 규칙의 임계값은 계약전력 대비 비율입니다(예: 0.9 = 90%). 계약전력이 없는 요금제면 판단하지 않습니다."
              : draft.alarmKind === "IDLE_USAGE"
                ? "MES 가동 구간 밖의 사용량을 봅니다. MES를 꺼 두면 판단하지 않습니다."
                : "그 달 시간 사용량의 최대값과 견줍니다."}
          </p>
        </div>
      )}
      {!alarms || !rules ? (
        !error && <Loading delay={300} />
      ) : (
        <div className="dashboard-grid has-lead">
          <section className="panel" aria-label="진행 중인 경보">
            <h2>진행 중인 경보 {open.length}건</h2>
            {open.length === 0 ? (
              <p className="muted">진행 중인 경보가 없습니다.</p>
            ) : (
              <div className="table-scroll">
                <table aria-label="진행 중인 경보">
                  <thead>
                    <tr>
                      <th scope="col">규칙</th>
                      <th scope="col">종류</th>
                      <th scope="col" className="num">
                        값 / 임계
                      </th>
                      <th scope="col">발생</th>
                      <th scope="col">상태</th>
                      <th scope="col">관리</th>
                    </tr>
                  </thead>
                  <tbody>
                    {open.map((a) => (
                      <tr key={a.id}>
                        <td>
                          {a.ruleCode} {a.ruleName}
                        </td>
                        <td>{KIND_LABEL[a.alarmKind]}</td>
                        <td className="num">
                          {num(a.peakValue)} / {num(a.threshold)} {a.unit}
                        </td>
                        <td>{when(a.raisedAt)}</td>
                        <td>
                          <Badge
                            tone={a.status === "OPEN" ? "issue" : "warning"}
                          >
                            {STATUS_LABEL[a.status]}
                          </Badge>
                        </td>
                        <td>
                          <span className="row-actions">
                            {a.status === "OPEN" && (
                              <button
                                type="button"
                                className="link-button"
                                disabled={pending}
                                onClick={() =>
                                  void send(`/alarms/${a.id}/acknowledge`)
                                }
                              >
                                확인
                              </button>
                            )}
                            <button
                              type="button"
                              className="link-button"
                              disabled={pending}
                              onClick={() => void send(`/alarms/${a.id}/clear`)}
                            >
                              해제
                            </button>
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
          <section className="panel" aria-label="경보 규칙">
            <h2>경보 규칙 {rules.length}개</h2>
            {rules.length === 0 ? (
              <p className="muted">
                규칙이 없습니다. 규칙 추가로 무엇을 볼지 정하세요.
              </p>
            ) : (
              <ul className="rank-list">
                {rules.map((r) => (
                  <li key={r.id}>
                    <span>
                      {r.code} {r.name} · {KIND_LABEL[r.alarmKind]}
                      {!r.isActive && <small className="muted"> (중지)</small>}
                    </span>
                    <span>
                      {num(r.threshold)} {r.unit}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </>
  );
}
