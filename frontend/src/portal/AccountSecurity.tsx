import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useSession } from "../app/session";
import { api } from "../shared/api";
import { ErrorNotice, Field, Loading } from "../shared/components";
import "./AccountSecurity.css";

type Summary = {
  mfaRegistered: boolean;
  recoveryCodesRemaining: number;
  assurance: string;
};
type Pending = {
  factorId: string;
  setupKey: string;
  provisioningUri: string;
  expiresInSeconds: number;
};
export function AccountSecurity({ recovery = false }: { recovery?: boolean }) {
  const {
    session,
    setSession,
    setBusy: setGlobalBusy,
    setNavigationBlocked,
  } = useSession();
  const navigate = useNavigate();
  const [summary, setSummary] = useState<Summary>();
  const [csrf, setCsrf] = useState(session?.csrfToken ?? "");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState<Pending>();
  const [code, setCode] = useState("");
  const [codes, setCodes] = useState<string[]>();
  const [ack, setAck] = useState(false);
  const [verified, setVerified] = useState(false);
  const [rotateAck, setRotateAck] = useState(false);
  const [notice, setNotice] = useState("");
  const [sessions, setSessions] = useState<
    { id: string; current: boolean; createdAt: string; method: string }[]
  >([]);

  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>();
  const errorFocus = useRef<HTMLDivElement>(null);
  useEffect(() => {
    setGlobalBusy(busy);
    return () => setGlobalBusy(false);
  }, [busy, setGlobalBusy]);
  useEffect(() => {
    setNavigationBlocked(Boolean(codes));
    return () => setNavigationBlocked(false);
  }, [codes, setNavigationBlocked]);

  useEffect(() => {
    let active = true;
    const load = recovery
      ? api<{ csrfToken: string }>("/security/recovery/status").then((r) => {
          if (active) setCsrf(r.data.csrfToken);
        })
      : api<Summary>("/security/me").then((r) => {
          if (active) setSummary(r.data);
        });
    load
      .catch((e) => {
        if (active) setError(e);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [recovery]);
  useEffect(() => {
    if (!codes) return;
    const guard = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", guard);
    return () => window.removeEventListener("beforeunload", guard);
  }, [codes]);
  async function start() {
    setBusy(true);
    setError(undefined);
    try {
      const r = await api<Pending>(
        recovery ? "/security/recovery/start" : "/security/enrollment/start",
        { method: "POST", csrf, ...(recovery ? {} : { body: { password } }) },
      );
      setPassword("");
      setPending(r.data);
      setCode("");
    } catch (e) {
      setError(e);
      requestAnimationFrame(() => errorFocus.current?.focus());
    } finally {
      setBusy(false);
    }
  }
  async function confirm() {
    if (!pending) return;
    setBusy(true);
    setError(undefined);
    try {
      const r = await api<{ recoveryCodes: string[] }>(
        recovery
          ? "/security/recovery/complete"
          : "/security/enrollment/confirm",
        { method: "POST", csrf, body: { factorId: pending.factorId, code } },
      );
      setPending(undefined);
      setCode("");
      setCodes(r.data.recoveryCodes);
      // Keep this one-time view visible after server-side session revocation.
    } catch (e) {
      setError(e);
      requestAnimationFrame(() => errorFocus.current?.focus());
    } finally {
      setBusy(false);
    }
  }
  async function secureAction(
    action: "step-up" | "recovery-codes/rotate" | "sessions/revoke-others",
  ) {
    setBusy(true);
    setError(undefined);
    setNotice("");
    try {
      const result = await api<{
        recoveryCodes?: string[];
        revokedCount?: number;
      }>("/security/" + action, {
        method: "POST",
        csrf,
        ...(action === "step-up" ? { body: { code } } : {}),
      });
      setCode("");
      if (action === "step-up") {
        setVerified(true);
        setNotice("본인 확인을 마쳤습니다. 5분 안에 처리하세요.");
      } else if (result.data.recoveryCodes) {
        setAck(false);
        setCodes(result.data.recoveryCodes);
        setSessions([]);
      } else {
        setNotice("다른 세션을 종료했습니다.");
        setVerified(false);
        setSessions([]);
      }
    } catch (e) {
      setError(e);
      requestAnimationFrame(() => errorFocus.current?.focus());
    } finally {
      setBusy(false);
    }
  }
  async function loadSessions() {
    setBusy(true);
    setError(undefined);
    try {
      const result = await api<{ sessions: typeof sessions }>(
        "/security/sessions",
      );
      setSessions(result.data.sessions);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  async function leaveRecovery() {
    setBusy(true);
    setError(undefined);
    try {
      await api("/security/recovery/logout", { method: "POST", csrf });
      setSession(null);
      navigate("/");
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  if (loading) return <Loading label="계정 보안 상태 확인 중" />;
  return (
    <section className="account-security" aria-busy={busy}>
      <h1>{recovery ? "인증 앱 다시 등록" : "내 계정 보안"}</h1>
      <p>
        {recovery
          ? "복구 중에는 문서·결재 등 업무에 접근할 수 없습니다. 새 인증 앱 등록을 마친 뒤 다시 로그인하세요."
          : "인증 앱을 등록하면 비밀번호 다음에 앱의 번호로 본인을 확인합니다."}
      </p>
      <Link to="/help/portal/account-security">인증·복구 도움말</Link>
      <div ref={errorFocus} tabIndex={-1}>
        <ErrorNotice error={error} />
      </div>
      {codes ? (
        <section aria-label="일회용 복구 코드">
          <h2>복구 코드를 지금 보관하세요</h2>
          <p>
            이 화면에서 한 번만 표시됩니다. 비밀번호와 다른 안전한 장소에
            보관하세요. 등록 전 세션은 모두 종료되었습니다.
          </p>
          <ul>
            {codes.map((c) => (
              <li key={c}>
                <code>{c}</code>
              </li>
            ))}
          </ul>
          <label>
            <input
              type="checkbox"
              checked={ack}
              onChange={(e) => setAck(e.target.checked)}
            />
            코드 8개를 안전하게 보관했습니다
          </label>
          <button
            disabled={!ack}
            onClick={() => {
              setCodes(undefined);
              setSession(null);
              navigate("/");
            }}
          >
            로그인 화면으로
          </button>
        </section>
      ) : pending ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void confirm();
          }}
        >
          <h2>앱에 설정 키 추가</h2>
          <p>
            인증 앱에서 계정 추가 → 설정 키 직접 입력을 선택하세요. 계정 이름은
            Factory Studio, 종류는 시간 기반입니다. 등록은 10분 안에 마쳐
            주세요.
          </p>
          <label>
            설정 키
            <input
              value={pending.setupKey}
              readOnly
              spellCheck={false}
              autoComplete="off"
              aria-label="인증 앱 설정 키"
            />
          </label>
          <p>
            설정 키를 다른 사람에게 보내지 마세요. 앱에 나타난 번호를 입력해야
            등록됩니다.
          </p>
          <Field
            label="인증 앱 번호"
            inputMode="numeric"
            autoComplete="one-time-code"
            required
            minLength={6}
            maxLength={6}
            value={code}
            onChange={(e) => setCode(e.target.value)}
            disabled={busy}
          />
          <button disabled={busy} type="submit">
            번호 확인하고 등록
          </button>
          <button
            disabled={busy}
            type="button"
            onClick={() => {
              setPending(undefined);
              setCode("");
              setError(undefined);
            }}
          >
            등록 취소
          </button>
        </form>
      ) : summary?.mfaRegistered ? (
        <section>
          <h2>인증 앱 등록됨</h2>
          <p>미사용 복구 코드 {summary.recoveryCodesRemaining}개</p>
          <p>설정 키와 이미 발급한 복구 코드는 다시 표시하지 않습니다.</p>
          <button disabled={busy} onClick={() => void loadSessions()}>
            접속 중인 세션 보기
          </button>
          {sessions.length > 0 && (
            <ul>
              {sessions.map((item) => (
                <li key={item.id}>
                  {item.current ? "현재 접속" : "다른 접속"} ·{" "}
                  {new Date(item.createdAt).toLocaleString("ko-KR")} ·{" "}
                  {item.method === "TOTP" ? "인증 앱" : "비밀번호"}
                </li>
              ))}
            </ul>
          )}
          <h3>추가 본인 확인</h3>
          <p>
            다른 세션 종료와 복구 코드 재발급 전에 확인합니다. 방금 로그인에
            사용한 번호는 다음 번호로 바뀐 뒤 입력하세요.
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void secureAction("step-up");
            }}
          >
            <Field
              label="추가 확인 번호"
              required
              inputMode="numeric"
              autoComplete="one-time-code"
              minLength={6}
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value)}
              disabled={busy}
            />
            <button type="submit" disabled={busy}>
              본인 확인
            </button>
          </form>
          {notice && <p role="status">{notice}</p>}
          <button
            disabled={busy || !verified}
            onClick={() => void secureAction("sessions/revoke-others")}
          >
            다른 세션 모두 종료
          </button>
          <p>
            재발급하면 이전 코드와 모든 세션이 종료됩니다. 새 코드 보관 후 다시
            로그인해야 합니다.
          </p>
          <label>
            <input
              type="checkbox"
              checked={rotateAck}
              onChange={(e) => setRotateAck(e.target.checked)}
            />
            이전 코드와 모든 세션을 회수하고 새 코드를 보관하겠습니다
          </label>
          <button
            disabled={busy || !verified || !rotateAck}
            onClick={() => void secureAction("recovery-codes/rotate")}
          >
            복구 코드 8개 새로 발급
          </button>
        </section>
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void start();
          }}
        >
          <h2>{recovery ? "새 인증 앱 연결" : "인증 앱 등록"}</h2>
          {!recovery && (
            <Field
              label="현재 비밀번호"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={busy}
            />
          )}
          <button
            disabled={busy || (!recovery && !password) || !csrf}
            type="submit"
          >
            {recovery ? "새 설정 키 받기" : "설정 키 받기"}
          </button>
        </form>
      )}
      {recovery && !codes && (
        <button disabled={busy} onClick={() => void leaveRecovery()}>
          복구 중단하고 나가기
        </button>
      )}
    </section>
  );
}
