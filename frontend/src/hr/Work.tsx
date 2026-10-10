import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useSession } from "../app/session";
import { api, ApiError } from "../shared/api";
import { ErrorNotice } from "../shared/components";
import "./Work.css";

type Company = {
  id: number;
  name: string;
  isExample: boolean;
  timezone: string;
};
type Clock = {
  id: number;
  employee_id: number;
  employeeName: string;
  work_date: string;
  clock_in: string;
  clock_out: string | null;
};
type Request = {
  id: number;
  employee_id: number;
  employeeName: string;
  kind: string;
  starts_at: string;
  ends_at: string;
  minutes: number;
  reason: string;
  destination: string | null;
  status: string;
};
type Overview = {
  company: Company;
  person: { id: number; name: string; role: string };
  policy: {
    daily_minutes: number;
    annual_days: number;
    start_time: string;
    end_time: string;
    break_start: string;
    break_end: string;
  };
  month: string;
  remainingMinutes: number;
  activeSession: Clock | null;
  sessions: Clock[];
  requests: Request[];
  events: { id: number; action: string; created_at: string }[];
  closed: boolean;
};
const labels: Record<string, string> = {
  ANNUAL: "연차",
  HALF_AM: "오전 반차",
  HALF_PM: "오후 반차",
  HOURLY: "시간차",
  TRIP: "출장",
  REQUESTED: "승인 대기",
  APPROVED: "승인",
  REJECTED: "반려",
  CANCELLED: "취소",
  CANCEL_REQUESTED: "취소 승인 대기",
};
function dateKst() {
  return new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Seoul" }).format(
    new Date(),
  );
}
function time(value: string | null) {
  return value
    ? new Intl.DateTimeFormat("ko-KR", {
        timeZone: "Asia/Seoul",
        dateStyle: "short",
        timeStyle: "short",
      }).format(new Date(value))
    : "—";
}
export function Work({ demo = false }: { demo?: boolean }) {
  const { session, setBusy, setNavigationBlocked } = useSession();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [companyId, setCompanyId] = useState<number>();
  const [data, setData] = useState<Overview>();
  const [month, setMonth] = useState(dateKst().slice(0, 7));
  const [error, setError] = useState<unknown>();
  const [pending, setPending] = useState(false);
  const [notice, setNotice] = useState("");
  const [online, setOnline] = useState(navigator.onLine);
  const [kind, setKind] = useState("HOURLY");
  const [day, setDay] = useState(dateKst());
  const [endDay, setEndDay] = useState(dateKst());
  const [from, setFrom] = useState("09:00");
  const [to, setTo] = useState("10:00");
  const [reason, setReason] = useState("");
  const [destination, setDestination] = useState("");
  const [correction, setCorrection] = useState<{
    id: number;
    clockIn: string;
    clockOut: string;
    reason: string;
  }>();
  const [demoRole, setDemoRole] = useState("STAFF");
  const [demoClock, setDemoClock] = useState<Clock>();
  const [demoRequests, setDemoRequests] = useState<Request[]>([]);
  const retry = useRef<{ path: string; body: unknown; key: string } | null>(
    null,
  );
  const alive = useRef(true);
  const base = `/api/v1/hr/work`;
  useEffect(() => {
    alive.current = true;
    const on = () => setOnline(navigator.onLine);
    window.addEventListener("online", on);
    window.addEventListener("offline", on);
    return () => {
      alive.current = false;
      window.removeEventListener("online", on);
      window.removeEventListener("offline", on);
    };
  }, []);
  useEffect(() => {
    if (demo || session?.actorKind !== "MEMBER") return;
    const abort = new AbortController();
    api<Company[]>(`${base}/companies`, { signal: abort.signal })
      .then((r) => {
        setCompanies(r.data);
        setCompanyId(r.data[0]?.id);
      })
      .catch((e) => {
        if (!abort.signal.aborted) setError(e);
      });
    return () => abort.abort();
  }, [demo, session?.actorKind]);
  useEffect(() => {
    if (
      !demo &&
      session?.actorKind === "MEMBER" &&
      "serviceWorker" in navigator &&
      import.meta.env.PROD
    )
      void navigator.serviceWorker
        .register("/work-sw.js")
        .catch(() =>
          setNotice(
            "앱 설치 준비에 실패했습니다. 웹 화면은 계속 사용할 수 있습니다.",
          ),
        );
  }, [demo, session?.actorKind]);
  async function load() {
    if (!companyId) return;
    const r = await api<Overview>(
      `${base}/overview?companyId=${companyId}&month=${month}`,
    );
    if (alive.current) setData(r.data);
  }
  useEffect(() => {
    if (!companyId) return;
    const abort = new AbortController();
    setData(undefined);
    api<Overview>(`${base}/overview?companyId=${companyId}&month=${month}`, {
      signal: abort.signal,
    })
      .then((r) => setData(r.data))
      .catch((e) => {
        if (!abort.signal.aborted) setError(e);
      });
    return () => abort.abort();
  }, [companyId, month]);
  async function send(path: string, body: unknown = undefined, replay = false) {
    if (pending || !online || !companyId || (!replay && retry.current)) return;
    const request = replay
      ? retry.current!
      : {
          path: `${base}${path}?companyId=${companyId}`,
          body,
          key: crypto.randomUUID(),
        };
    retry.current = request;
    setPending(true);
    setBusy(true);
    setNavigationBlocked(true);
    setError(undefined);
    try {
      await api(request.path, {
        method: "POST",
        body: request.body,
        csrf: session?.csrfToken,
        key: request.key,
      });
      retry.current = null;
      setNotice("처리했습니다.");
      await load();
    } catch (e) {
      if (!(e instanceof ApiError) || e.status === 0 || e.status >= 500) {
        setError(e);
      } else {
        retry.current = null;
        setError(e);
      }
    } finally {
      setPending(false);
      setBusy(false);
      setNavigationBlocked(retry.current !== null);
    }
  }
  if (!demo && session?.actorKind !== "MEMBER")
    return (
      <section className="work-page">
        <h1>내 근무</h1>
        <p>회사 근무는 로그인 회원만 이용할 수 있습니다.</p>
        <Link to="/hr/work-demo">합성 데이터로 근무 체험하기</Link>
        <p>
          <Link to="/">회원 로그인</Link>
        </p>
      </section>
    );
  const person = demo
    ? { id: 2, name: "예제 직원", role: demoRole }
    : data?.person;
  const requests = demo ? demoRequests : (data?.requests ?? []);
  const clocks = demo ? (demoClock ? [demoClock] : []) : (data?.sessions ?? []);
  const active = demo
    ? demoClock && !demoClock.clock_out
      ? demoClock
      : null
    : data?.activeSession;
  const locked =
    pending || !online || retry.current !== null || (!demo && !data);
  function clock(out: boolean) {
    if (!demo) {
      void send(`/clock/${out ? "clock-out" : "clock-in"}`);
      return;
    }
    setDemoClock({
      id: 1,
      employee_id: 2,
      employeeName: "예제 직원",
      work_date: dateKst(),
      clock_in: `${dateKst()}T09:00:00+09:00`,
      clock_out: out ? `${dateKst()}T18:00:00+09:00` : null,
    });
    setNotice("합성 예제 시각으로 기록했습니다. 실제 출퇴근 기록이 아닙니다.");
  }
  function submit(e: React.FormEvent) {
    e.preventDefault();
    let a = from,
      b = to,
      finish = day;
    if (kind === "ANNUAL") {
      a = "09:00";
      b = "18:00";
      finish = endDay;
    }
    if (kind === "HALF_AM") {
      a = "09:00";
      b = "14:00";
    }
    if (kind === "HALF_PM") {
      a = "14:00";
      b = "18:00";
    }
    if (kind === "TRIP") finish = endDay;
    const body = {
      kind,
      startsAt: `${day}T${a}:00+09:00`,
      endsAt: `${finish}T${b}:00+09:00`,
      reason,
      destination: kind === "TRIP" ? destination : null,
    };
    if (demo) {
      const mins =
        kind === "TRIP"
          ? 0
          : kind === "ANNUAL"
            ? 480
            : kind === "HOURLY"
              ? Math.max(
                  0,
                  (Date.parse(body.endsAt) - Date.parse(body.startsAt)) /
                    60000 -
                    (a < "13:00" && b > "12:00"
                      ? Math.max(
                          0,
                          Math.min(
                            Date.parse(`${day}T13:00:00+09:00`),
                            Date.parse(body.endsAt),
                          ) -
                            Math.max(
                              Date.parse(`${day}T12:00:00+09:00`),
                              Date.parse(body.startsAt),
                            ),
                        ) / 60000
                      : 0),
                )
              : 240;
      if (
        Date.parse(body.endsAt) <= Date.parse(body.startsAt) ||
        (kind === "HOURLY" && (mins <= 0 || mins % 60 !== 0))
      ) {
        setNotice("시간차는 휴게시간을 제외한 1시간 단위로 선택하세요.");
        return;
      }
      setDemoRequests((v) => [
        {
          id: Date.now(),
          employee_id: 2,
          employeeName: "예제 직원",
          kind,
          starts_at: body.startsAt,
          ends_at: body.endsAt,
          minutes: mins,
          reason,
          destination: body.destination,
          status: "REQUESTED",
        },
        ...v,
      ]);
      setNotice(
        "합성 체험 신청을 추가했습니다. 회사 기록에는 저장되지 않습니다.",
      );
      return;
    }
    void send("/requests", body);
  }
  function decide(id: number, op: string) {
    if (demo) {
      setDemoRequests((v) =>
        v.map((r) =>
          r.id === id
            ? {
                ...r,
                status:
                  op === "approve"
                    ? "APPROVED"
                    : op === "reject"
                      ? "REJECTED"
                      : "CANCELLED",
              }
            : r,
        ),
      );
      return;
    }
    void send(`/requests/${op}`, { id });
  }
  return (
    <section className="work-page" aria-busy={pending}>
      <header className="work-heading">
        <div>
          <p>{demo ? "합성 데이터 체험" : "회사 공동 근무"}</p>
          <h1>{demo ? "근무 체험" : "내 근무"}</h1>
          <p>
            {demo
              ? "hugh-D Company · 화면을 닫으면 체험 기록은 사라집니다."
              : `${data?.company.name ?? "회사 연결 확인"} · ${person?.name ?? ""}`}
          </p>
        </div>
        <Link to={demo ? "/hr/work" : "/hr/work-demo"}>
          {demo ? "실제 근무로" : "체험 화면"}
        </Link>
      </header>
      {!demo && (
        <aside className="work-install">
          <strong>휴대폰 홈 화면에 설치</strong>
          <p>
            Android: 브라우저 메뉴 → 앱 설치 · iPhone: Safari 공유 → 홈 화면에
            추가. 실제 기록은 인터넷 연결 후 서버에서 저장합니다.
          </p>
        </aside>
      )}
      {demo && (
        <label>
          체험 역할
          <select
            aria-label="체험 역할"
            value={demoRole}
            onChange={(e) => setDemoRole(e.target.value)}
          >
            <option value="STAFF">직원</option>
            <option value="ADMIN">관리자 · 합성 신청 승인</option>
          </select>
        </label>
      )}
      {!demo && companies.length > 0 && (
        <label>
          회사
          <select
            disabled={locked}
            value={companyId}
            onChange={(e) => setCompanyId(Number(e.target.value))}
          >
            {companies.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
                {c.isExample ? " · 예제" : ""}
              </option>
            ))}
          </select>
        </label>
      )}
      {!demo && !error && companies.length === 0 && (
        <p>회사 소속이 없으면 관리자에게 계정·사원 연결을 요청하세요.</p>
      )}
      {!online && (
        <p role="alert">
          오프라인입니다. 출퇴근 기록과 신청은 연결 후 다시 진행하세요.
        </p>
      )}
      <ErrorNotice
        error={error}
        retry={
          retry.current
            ? () => void send("", undefined, true)
            : () => void load()
        }
      />
      <p role="status">{notice}</p>
      {(demo || data) && (
        <>
          <div className="work-summary">
            <article>
              <span>오늘 근무 상태</span>
              <h2>{active ? "근무 중" : "출근 전 또는 퇴근 완료"}</h2>
              <p>
                {active
                  ? `출근 ${time(active.clock_in)}`
                  : demo
                    ? "합성 예제 시각으로 출퇴근을 체험합니다."
                    : "서버 시각으로 출근·퇴근을 기록합니다."}
              </p>
              <div className="actions">
                <button
                  disabled={
                    locked ||
                    !!active ||
                    clocks.some(
                      (c) =>
                        c.employee_id === person?.id &&
                        c.work_date === dateKst(),
                    )
                  }
                  onClick={() => clock(false)}
                >
                  출근하기
                </button>
                <button
                  disabled={locked || !active}
                  onClick={() => clock(true)}
                >
                  퇴근하기
                </button>
              </div>
            </article>
            <article>
              <span>{month.slice(0, 4)}년 연차 잔여</span>
              <h2>
                {(
                  (demo
                    ? 7200 -
                      demoRequests
                        .filter((r) => r.status === "APPROVED")
                        .reduce((s, r) => s + r.minutes, 0)
                    : data!.remainingMinutes) / 60
                ).toLocaleString()}
                시간
              </h2>
              <p>예제 기준 1일 8시간 · 연차 15일</p>
              <p>09:00~18:00 · 휴게 12:00~13:00</p>
            </article>
          </div>
          <section className="work-card">
            <h2>휴가·시간차·출장 신청</h2>
            <form onSubmit={submit} className="work-form">
              <label>
                종류
                <select
                  disabled={locked}
                  value={kind}
                  onChange={(e) => setKind(e.target.value)}
                >
                  {["HOURLY", "ANNUAL", "HALF_AM", "HALF_PM", "TRIP"].map(
                    (k) => (
                      <option key={k} value={k}>
                        {labels[k]}
                      </option>
                    ),
                  )}
                </select>
              </label>
              <label>
                시작일
                <input
                  type="date"
                  required
                  disabled={locked}
                  value={day}
                  onChange={(e) => {
                    setDay(e.target.value);
                    setEndDay(e.target.value);
                  }}
                />
              </label>
              {(kind === "ANNUAL" || kind === "TRIP") && (
                <label>
                  종료일
                  <input
                    type="date"
                    required
                    disabled={locked}
                    min={day}
                    value={endDay}
                    onChange={(e) => setEndDay(e.target.value)}
                  />
                </label>
              )}
              {(kind === "HOURLY" || kind === "TRIP") && (
                <>
                  <label>
                    시작 시간
                    <input
                      type="time"
                      required
                      disabled={locked}
                      step={3600}
                      value={from}
                      onChange={(e) => setFrom(e.target.value)}
                    />
                  </label>
                  <label>
                    종료 시간
                    <input
                      type="time"
                      required
                      disabled={locked}
                      step={3600}
                      value={to}
                      onChange={(e) => setTo(e.target.value)}
                    />
                  </label>
                </>
              )}
              {kind === "TRIP" && (
                <label>
                  행선지
                  <input
                    required
                    disabled={locked}
                    maxLength={200}
                    value={destination}
                    onChange={(e) => setDestination(e.target.value)}
                  />
                </label>
              )}
              <label className="work-form-reason">
                사유
                <textarea
                  required
                  minLength={2}
                  maxLength={500}
                  disabled={locked}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                />
              </label>
              <p>
                시간차는 휴게시간을 제외한 1시간 단위입니다. 오전 반차
                09~14시(휴게 포함), 오후 반차 14~18시. 출장은 연차를 차감하지
                않습니다.
              </p>
              <button disabled={locked}>신청하기</button>
            </form>
          </section>
          <section className="work-card">
            <h2>신청 내역{person?.role === "ADMIN" ? " · 회사 직원" : ""}</h2>
            {requests.length === 0 ? (
              <p>신청 내역이 없습니다.</p>
            ) : (
              requests.map((r) => (
                <article className="work-record" key={r.id}>
                  <div>
                    <strong>
                      {r.employeeName} · {labels[r.kind]} · {labels[r.status]}
                    </strong>
                    <p>
                      {time(r.starts_at)} ~ {time(r.ends_at)} · 차감{" "}
                      {r.minutes / 60}시간
                    </p>
                    <p>
                      {r.reason}
                      {r.destination ? ` · ${r.destination}` : ""}
                    </p>
                  </div>
                  <div className="actions">
                    {(r.status === "REQUESTED" ||
                      r.status === "CANCEL_REQUESTED") &&
                      person?.role === "ADMIN" &&
                      (demo || r.employee_id !== person.id) && (
                        <>
                          <button
                            disabled={locked}
                            onClick={() => decide(r.id, "approve")}
                          >
                            승인
                          </button>
                          <button
                            disabled={locked}
                            onClick={() => decide(r.id, "reject")}
                          >
                            반려
                          </button>
                        </>
                      )}
                    {(r.status === "REQUESTED" || r.status === "APPROVED") &&
                      (demo || r.employee_id === person?.id) && (
                        <button
                          disabled={locked}
                          onClick={() => decide(r.id, "cancel")}
                        >
                          신청 취소
                        </button>
                      )}
                  </div>
                </article>
              ))
            )}
          </section>
          <section className="work-card">
            <h2>출퇴근 기록{person?.role === "ADMIN" ? " · 회사 직원" : ""}</h2>
            <label>
              조회 월
              <input
                type="month"
                disabled={locked}
                value={month}
                onChange={(e) => setMonth(e.target.value)}
              />
            </label>
            {clocks.length === 0 ? (
              <p>출퇴근 기록이 없습니다.</p>
            ) : (
              clocks.map((r) => (
                <article className="work-record" key={r.id}>
                  <div>
                    <strong>
                      {r.employeeName} · {r.work_date}
                    </strong>
                    <p>
                      출근 {time(r.clock_in)} · 퇴근 {time(r.clock_out)}
                    </p>
                    {!demo && person?.role === "ADMIN" && (
                      <button
                        disabled={locked || data?.closed}
                        onClick={() =>
                          setCorrection({
                            id: r.id,
                            clockIn: new Date(
                              new Date(r.clock_in).getTime() + 9 * 3600000,
                            )
                              .toISOString()
                              .slice(0, 23),
                            clockOut: r.clock_out
                              ? new Date(
                                  new Date(r.clock_out).getTime() + 9 * 3600000,
                                )
                                  .toISOString()
                                  .slice(0, 23)
                              : "",
                            reason: "",
                          })
                        }
                      >
                        기록 정정
                      </button>
                    )}
                  </div>
                </article>
              ))
            )}
            {data?.closed && <p>마감한 월입니다. 기록을 변경할 수 없습니다.</p>}
          </section>
          {correction && (
            <section className="work-card">
              <h2>출퇴근 기록 정정</h2>
              <form
                className="work-form"
                onSubmit={(e) => {
                  e.preventDefault();
                  void send("/corrections", {
                    id: correction.id,
                    clockIn:
                      correction.clockIn +
                      (correction.clockIn.length === 16 ? ":00" : "") +
                      "+09:00",
                    clockOut: correction.clockOut
                      ? correction.clockOut +
                        (correction.clockOut.length === 16 ? ":00" : "") +
                        "+09:00"
                      : null,
                    reason: correction.reason,
                  });
                }}
              >
                <label>
                  출근 시각
                  <input
                    type="datetime-local"
                    step="0.001"
                    required
                    disabled={locked}
                    value={correction.clockIn}
                    onChange={(e) =>
                      setCorrection({ ...correction, clockIn: e.target.value })
                    }
                  />
                </label>
                <label>
                  퇴근 시각
                  <input
                    type="datetime-local"
                    step="0.001"
                    disabled={locked}
                    value={correction.clockOut}
                    onChange={(e) =>
                      setCorrection({ ...correction, clockOut: e.target.value })
                    }
                  />
                </label>
                <label>
                  정정 사유
                  <input
                    required
                    minLength={2}
                    maxLength={500}
                    disabled={locked}
                    value={correction.reason}
                    onChange={(e) =>
                      setCorrection({ ...correction, reason: e.target.value })
                    }
                  />
                </label>
                <button disabled={locked}>이력 남기고 정정</button>
                <button
                  type="button"
                  disabled={locked}
                  onClick={() => setCorrection(undefined)}
                >
                  정정 닫기
                </button>
              </form>
            </section>
          )}
          {person?.role === "ADMIN" && !demo && (
            <section className="work-card">
              <h2>월 마감</h2>
              <p>미처리 신청과 퇴근 누락을 확인한 뒤 종료된 월을 마감합니다.</p>
              <button
                disabled={locked || data?.closed}
                onClick={() => void send("/close", { month })}
              >
                {month} 마감
              </button>
              <h3>변경 이력</h3>
              {data?.events.map((e) => (
                <p key={e.id}>
                  {time(e.created_at)} · {e.action}
                </p>
              ))}
            </section>
          )}
        </>
      )}
    </section>
  );
}
