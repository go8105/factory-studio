// F-15 계측 품질 — 결측·이상값 탐지와 보정, CSV 올리기 (DSN-15 F12·F13·F14)
// 보정은 원 계측을 지우지 않는다. 새 입력 수정 버전으로 들어가고 원 값은 이력에 남는다.
import { useEffect, useState, type ChangeEvent } from "react";
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

type Meter = {
  id: number;
  meterCode: string;
  name: string;
  channels: { id: number; channelCode: string; name: string }[];
};
type Issue = {
  kind: "MISSING" | "ZERO_RUN" | "SPIKE";
  periodStart: string;
  value: string | null;
  note: string;
};
type Correction = {
  id: number;
  channelCode: string;
  periodStart: string;
  originalValue: string | null;
  correctedValue: string;
  method: string;
  reason: string;
  correctedAt: string;
};
type Quality = {
  channel: {
    id: number;
    channelCode: string;
    name: string;
    unit: string;
  } | null;
  period: { from: string; to: string } | null;
  readingCount: number;
  issues: Issue[];
  corrections: Correction[];
};

const KIND_LABEL: Record<Issue["kind"], string> = {
  MISSING: "결측",
  ZERO_RUN: "0 연속",
  SPIKE: "급증",
};
const METHOD_LABEL: Record<string, string> = {
  INTERPOLATE: "보간",
  PREVIOUS: "직전값",
  MANUAL: "수동",
};
const when = (iso: string) =>
  new Date(iso).toLocaleString("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    hourCycle: "h23",
  });

/** CSV 한 장을 브라우저에서 푼다. 서버는 행만 받는다. */
function parseCsv(
  text: string,
): { channelCode: string; periodStart: string; value: string }[] {
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith("#"))
    .map((line) => line.split(","))
    .filter((cells) => cells.length >= 3 && !/^채널|^channel/i.test(cells[0]))
    .map(([channelCode, periodStart, value]) => ({
      channelCode: channelCode.trim(),
      periodStart: periodStart.trim(),
      value: value.trim(),
    }));
}

export function ReadingQuality() {
  const { session, fail } = useSession();
  const [meters, setMeters] = useState<Meter[]>([]);
  const [channelId, setChannelId] = useState("");
  const [data, setData] = useState<Quality>();
  const [error, setError] = useState<unknown>();
  const [reload, setReload] = useState(0);
  const [pending, setPending] = useState(false);
  const [done, setDone] = useState<string>();
  const [fixing, setFixing] = useState<Issue>();
  const [fix, setFix] = useState({
    value: "",
    method: "INTERPOLATE",
    reason: "",
  });
  const [upload, setUpload] = useState<{
    fileName: string;
    rows: { channelCode: string; periodStart: string; value: string }[];
  }>();

  useEffect(() => {
    api<Meter[]>("/api/v1/fems/meters")
      .then((r) => {
        setMeters(r.data);
        const first = r.data.flatMap((m) => m.channels)[0];
        if (first) setChannelId((id) => id || String(first.id));
      })
      .catch(setError);
  }, []);

  useEffect(() => {
    if (!channelId) return;
    const controller = new AbortController();
    setError(undefined);
    setData(undefined);
    api<Quality>(`/api/v1/fems/reading-quality?channelId=${channelId}`, {
      signal: controller.signal,
    })
      .then((r) => !controller.signal.aborted && setData(r.data))
      .catch((e) => {
        if (controller.signal.aborted) return;
        setError(e);
        if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
      });
    return () => controller.abort();
  }, [channelId, reload]);

  async function send<T>(path: string, body: unknown): Promise<T | undefined> {
    if (!session?.csrfToken) return undefined;
    setPending(true);
    setError(undefined);
    try {
      const response = await api<T>(`/api/v1/fems${path}`, {
        method: "POST",
        body,
        csrf: session.csrfToken,
        key: `fq-${Date.now()}`,
      });
      setReload((n) => n + 1);
      return response.data;
    } catch (e) {
      setError(e);
      return undefined;
    } finally {
      setPending(false);
    }
  }

  async function saveFix() {
    if (!fixing || !data?.channel) return;
    const saved = await send<{ correctedValue: string }>(
      "/reading-corrections",
      {
        channelId: data.channel.id,
        periodStart: fixing.periodStart,
        correctedValue: fix.value,
        method: fix.method,
        reason: fix.reason,
      },
    );
    if (saved) {
      setDone(`${when(fixing.periodStart)} 값을 보정했습니다.`);
      setFixing(undefined);
      setFix({ value: "", method: "INTERPOLATE", reason: "" });
    }
  }

  function pickFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    void file.text().then((text) => {
      const rows = parseCsv(text);
      setUpload({ fileName: file.name, rows });
      setDone(
        rows.length
          ? `${file.name}에서 ${rows.length}행을 읽었습니다. 올리기를 누르세요.`
          : `${file.name}에서 읽을 행이 없습니다.`,
      );
    });
  }

  async function sendUpload() {
    if (!upload?.rows.length) return;
    const saved = await send<{
      acceptedCount: number;
      rejectedCount: number;
      rejected: string[];
    }>("/reading-uploads", upload);
    if (saved) {
      setDone(
        `${saved.acceptedCount}행 반영, ${saved.rejectedCount}행 거부.` +
          (saved.rejected.length ? ` ${saved.rejected.join(" ")}` : ""),
      );
      setUpload(undefined);
    }
  }

  const errors = fieldErrors(error);
  const channels = meters.flatMap((m) =>
    m.channels.map((c) => ({ ...c, meterCode: m.meterCode })),
  );

  return (
    <>
      <PageTitle
        id="F-15"
        title="계측 품질"
        subtitle="결측·이상값을 찾아 보정하고, CSV로 계측을 올립니다"
        help="fems/f-15"
      />
      <ErrorNotice error={Object.keys(errors).length ? undefined : error} />
      {done && <p role="status">{done}</p>}
      <div className="filter-bar">
        <label>
          계측 채널
          <select
            value={channelId}
            onChange={(e) => setChannelId(e.target.value)}
          >
            {channels.map((c) => (
              <option key={c.id} value={c.id}>
                {c.meterCode} · {c.channelCode} {c.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          CSV 올리기
          <input type="file" accept=".csv,text/csv" onChange={pickFile} />
        </label>
        {upload && (
          <button
            type="button"
            disabled={pending}
            onClick={() => void sendUpload()}
          >
            {upload.rows.length}행 올리기
          </button>
        )}
      </div>
      <p className="muted" role="note">
        CSV는 <strong>채널코드, 구간시작, 값</strong> 세 칸입니다(머리글 한 줄은
        건너뜁니다). 파일은 브라우저에서 풀어 행만 보냅니다.{" "}
        <strong>이미 값이 있는 구간은 덮지 않습니다</strong> — 고치려면 아래
        보정을 쓰세요.
      </p>
      {!data ? (
        !error && <Loading delay={300} />
      ) : !data.channel ? (
        <p className="muted">계측값이 없습니다.</p>
      ) : (
        <div className="dashboard-grid has-lead">
          <section className="panel" aria-label="결측·이상값">
            <h2>
              결측·이상값 {data.issues.length}건{" "}
              <small className="muted">
                {data.period?.from} ~ {data.period?.to} · 계측{" "}
                {data.readingCount}건
              </small>
            </h2>
            {data.issues.length === 0 ? (
              <p className="muted">이 기간에는 찾은 문제가 없습니다.</p>
            ) : (
              <div className="table-scroll">
                <table aria-label="결측·이상값">
                  <thead>
                    <tr>
                      <th scope="col">구간</th>
                      <th scope="col">종류</th>
                      <th scope="col" className="num">
                        값
                      </th>
                      <th scope="col">근거</th>
                      <th scope="col">관리</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.issues.slice(0, 50).map((issue) => (
                      <tr key={`${issue.kind}-${issue.periodStart}`}>
                        <td>{when(issue.periodStart)}</td>
                        <td>
                          <Badge
                            tone={
                              issue.kind === "MISSING" ? "issue" : "warning"
                            }
                          >
                            {KIND_LABEL[issue.kind]}
                          </Badge>
                        </td>
                        <td className="num">{issue.value ?? "—"}</td>
                        <td className="wrap">{issue.note}</td>
                        <td>
                          <button
                            type="button"
                            className="link-button"
                            aria-pressed={
                              fixing?.periodStart === issue.periodStart
                            }
                            onClick={() => {
                              setFixing(issue);
                              setFix({
                                value: issue.value ?? "",
                                method:
                                  issue.kind === "MISSING"
                                    ? "INTERPOLATE"
                                    : "MANUAL",
                                reason: "",
                              });
                            }}
                          >
                            보정
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {fixing && (
              <div className="section-block">
                <h3>{when(fixing.periodStart)} 보정</h3>
                <p className="muted">
                  원 계측은 지우지 않습니다. 고친 값이 새 버전으로 들어가고 원
                  값은 이력에 남습니다.
                </p>
                <div className="field-row">
                  <Field
                    label={`보정 값 (${data.channel.unit})`}
                    inputMode="decimal"
                    value={fix.value}
                    required
                    error={errors.correctedValue}
                    onChange={(e) => setFix({ ...fix, value: e.target.value })}
                  />
                  <label>
                    방법
                    <select
                      value={fix.method}
                      onChange={(e) =>
                        setFix({ ...fix, method: e.target.value })
                      }
                    >
                      <option value="INTERPOLATE">보간</option>
                      <option value="PREVIOUS">직전값</option>
                      <option value="MANUAL">수동</option>
                    </select>
                  </label>
                </div>
                <Field
                  label="사유"
                  value={fix.reason}
                  required
                  maxLength={300}
                  error={errors.reason}
                  onChange={(e) => setFix({ ...fix, reason: e.target.value })}
                />
                <span className="row-actions">
                  <button
                    type="button"
                    disabled={
                      pending ||
                      !fix.value.trim() ||
                      fix.reason.trim().length < 2
                    }
                    onClick={() => void saveFix()}
                  >
                    보정 저장
                  </button>
                  <button
                    type="button"
                    className="link-button"
                    onClick={() => setFixing(undefined)}
                  >
                    취소
                  </button>
                </span>
              </div>
            )}
          </section>
          <section className="panel" aria-label="보정 이력">
            <h2>보정 이력</h2>
            {data.corrections.length === 0 ? (
              <p className="muted">보정한 기록이 없습니다.</p>
            ) : (
              <ul className="rank-list">
                {data.corrections.slice(0, 10).map((c) => (
                  <li key={c.id}>
                    <span>
                      {c.channelCode} · {when(c.periodStart)} ·{" "}
                      {METHOD_LABEL[c.method] ?? c.method}
                    </span>
                    <span>
                      {c.originalValue ?? "없음"} → {Number(c.correctedValue)}
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
