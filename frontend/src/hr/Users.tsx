import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useSession } from "../app/session";
import { api, ApiError } from "../shared/api";
import "./Work.css";

type Company = { id: number; name: string };
type User = {
  userId: number;
  loginId: string;
  employeeCode: string;
  name: string;
  role: "ADMIN" | "STAFF";
  active: boolean;
  isSelf?: boolean;
};
type Pending = { path: string; body: Record<string, unknown>; key: string };
const base = "/api/v1/hr/work";
export function Users() {
  const { session, setBusy, setNavigationBlocked } = useSession();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [companyId, setCompanyId] = useState<number>();
  const [rows, setRows] = useState<User[]>([]);
  const [editing, setEditing] = useState<User>();
  const [login, setLogin] = useState("");
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [role, setRole] = useState("STAFF");
  const [days, setDays] = useState("15");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [busy, setLocalBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const retry = useRef<Pending | null>(null);
  const locked = busy || retry.current !== null;
  useEffect(() => {
    if (session?.actorKind !== "MEMBER") {
      setLoading(false);
      return;
    }
    const abort = new AbortController();
    api<Company[]>(`${base}/managed-companies`, { signal: abort.signal })
      .then((r) => {
        setCompanies(r.data);
        setCompanyId(r.data[0]?.id);
        setLoading(false);
      })
      .catch((e) => {
        if (!abort.signal.aborted) {
          setError(e.message);
          setLoading(false);
        }
      });
    return () => abort.abort();
  }, [session?.actorKind]);
  useEffect(() => {
    if (!companyId) return;
    const abort = new AbortController();
    setRows([]);
    setEditing(undefined);
    api<User[]>(`${base}/users?companyId=${companyId}`, {
      signal: abort.signal,
    })
      .then((r) => setRows(r.data))
      .catch((e) => {
        if (!abort.signal.aborted) setError(e.message);
      });
    return () => abort.abort();
  }, [companyId]);
  useEffect(
    () => () => {
      retry.current = null;
      setBusy(false);
      setNavigationBlocked(false);
    },
    [setBusy, setNavigationBlocked],
  );
  function select(user?: User) {
    setEditing(user);
    setLogin(user?.loginId ?? "");
    setName(user?.name ?? "");
    setCode(user?.employeeCode ?? "");
    setRole(user?.role ?? "STAFF");
    setPassword("");
    setConfirmation("");
    setError("");
    setNotice("");
  }
  async function send(
    path: string,
    body: Record<string, unknown>,
    pending?: Pending,
  ) {
    if (!companyId || busy) return;
    const request = pending ?? {
      path: `${base}/users${path}?companyId=${companyId}`,
      body,
      key: crypto.randomUUID(),
    };
    retry.current = request;
    setLocalBusy(true);
    setBusy(true);
    setNavigationBlocked(true);
    setError("");
    setNotice("");
    setPassword("");
    setConfirmation("");
    try {
      await api(request.path, {
        method: "POST",
        body: request.body,
        key: request.key,
        csrf: session?.csrfToken,
      });
      retry.current = null;
      setNavigationBlocked(false);
      setNotice(
        "사용자 설정을 저장했습니다. 비밀번호·권한 변경 시 기존 로그인은 종료됩니다.",
      );
      const r = await api<User[]>(`${base}/users?companyId=${companyId}`);
      setRows(r.data);
      setEditing(undefined);
      setRole("STAFF");
      setDays("15");
      setLogin("");
      setName("");
      setCode("");
    } catch (e) {
      const err = e as ApiError;
      setError(err.message);
      if (err.status !== 0 && err.status < 500) {
        retry.current = null;
        setNavigationBlocked(false);
      }
    } finally {
      setLocalBusy(false);
      setBusy(false);
    }
  }
  function credential(path: string) {
    if (password.length < 10 || password !== confirmation) {
      setError("비밀번호는 10자 이상으로 두 번 동일하게 입력하세요.");
      return;
    }
    if (editing) void send(path, { userId: editing.userId, password });
    else
      void send("", {
        loginId: login.trim().toLowerCase(),
        name: name.trim(),
        employeeCode: code.trim(),
        role,
        annualDays: Number(days),
        password,
      });
  }
  if (session?.actorKind !== "MEMBER")
    return (
      <section className="work-page">
        <h1>사용자 관리</h1>
        <p>관리자 계정으로 로그인해 주세요.</p>
      </section>
    );
  return (
    <section className="work-page" aria-busy={busy}>
      <header className="work-heading">
        <div>
          <p>회사 관리자</p>
          <h1>사용자 관리</h1>
          <p>
            회사에 사용할 아이디를 추가하고 비밀번호와 근무 권한을 관리합니다.
          </p>
        </div>
        <Link to="/hr/work">내 근무</Link>
      </header>
      <p>
        비밀번호는 저장 후 확인할 수 없습니다. 비밀번호 설정은 비활성 계정을
        활성화하고 기존 로그인을 종료합니다.
      </p>
      {loading ? (
        <p role="status">관리 권한을 확인하고 있습니다.</p>
      ) : companies.length === 0 ? (
        <p>
          관리할 수 있는 회사가 없습니다. 회사 관리자 또는 전체 관리자 계정이
          필요합니다.
        </p>
      ) : (
        <>
          <label>
            관리할 회사
            <select
              value={companyId ?? ""}
              disabled={locked}
              onChange={(e) => setCompanyId(Number(e.target.value))}
            >
              {companies.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <section className="work-card">
            <h2>회사 사용자 {rows.length}명</h2>
            <button disabled={locked} onClick={() => select()}>
              + 사용자 추가
            </button>
            {rows.map((user) => (
              <article className="work-record" key={user.userId}>
                <div>
                  <strong>
                    {user.name} · {user.loginId}
                  </strong>
                  <p>
                    {user.employeeCode} ·{" "}
                    {user.role === "ADMIN" ? "회사 관리자" : "직원"} ·{" "}
                    {user.active ? "사용 중" : "비활성 · 비밀번호 설정 후 사용"}
                  </p>
                </div>
                <button disabled={locked} onClick={() => select(user)}>
                  계정 관리
                </button>
              </article>
            ))}
          </section>
          <section className="work-card">
            <h2>{editing ? `${editing.name} 계정 관리` : "새 사용자 추가"}</h2>
            {editing?.isSelf && (
              <p>
                현재 로그인한 관리자 계정은 다른 관리자에게 변경을 요청하세요.
              </p>
            )}
            <form
              className="work-form"
              onSubmit={(e) => {
                e.preventDefault();
                credential(editing ? "/password" : "");
              }}
            >
              <label>
                아이디
                <input
                  required
                  pattern="[a-z0-9][a-z0-9._-]{2,39}"
                  maxLength={40}
                  value={login}
                  disabled={locked}
                  onChange={(e) => setLogin(e.target.value.toLowerCase())}
                />
              </label>
              {!editing && (
                <>
                  <label>
                    직원 이름
                    <input
                      required
                      minLength={2}
                      maxLength={100}
                      value={name}
                      disabled={locked}
                      onChange={(e) => setName(e.target.value)}
                    />
                  </label>
                  <label>
                    사원 코드
                    <input
                      required
                      pattern="[A-Za-z0-9][A-Za-z0-9_-]{0,29}"
                      maxLength={30}
                      value={code}
                      disabled={locked}
                      onChange={(e) => setCode(e.target.value)}
                    />
                  </label>
                  <label>
                    올해 연차 부여 일수
                    <input
                      type="number"
                      min={0}
                      max={366}
                      step="0.01"
                      required
                      value={days}
                      disabled={locked}
                      onChange={(e) => setDays(e.target.value)}
                    />
                  </label>
                </>
              )}
              <label>
                근무 권한
                <select
                  value={role}
                  disabled={locked}
                  onChange={(e) => setRole(e.target.value)}
                >
                  <option value="STAFF">직원</option>
                  <option value="ADMIN">회사 관리자</option>
                </select>
              </label>
              <label>
                새 비밀번호
                <input
                  type="password"
                  autoComplete="new-password"
                  required
                  minLength={10}
                  maxLength={256}
                  value={password}
                  disabled={locked}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </label>
              <label>
                비밀번호 확인
                <input
                  type="password"
                  autoComplete="new-password"
                  required
                  minLength={10}
                  maxLength={256}
                  value={confirmation}
                  disabled={locked}
                  onChange={(e) => setConfirmation(e.target.value)}
                />
              </label>
              <button type="submit" disabled={locked || editing?.isSelf}>
                {editing ? "비밀번호 설정·사용 재개" : "사용자 추가"}
              </button>
              {editing && (
                <>
                  <button
                    type="button"
                    disabled={
                      locked || editing.isSelf || login === editing.loginId
                    }
                    onClick={() =>
                      void send("/login-id", {
                        userId: editing.userId,
                        loginId: login.trim().toLowerCase(),
                      })
                    }
                  >
                    아이디 변경
                  </button>
                  <button
                    type="button"
                    disabled={locked || editing.isSelf || role === editing.role}
                    onClick={() =>
                      void send("/role", { userId: editing.userId, role })
                    }
                  >
                    근무 권한 변경
                  </button>
                  {editing.active && (
                    <button
                      type="button"
                      disabled={locked || editing.isSelf}
                      onClick={() =>
                        void send("/disable", { userId: editing.userId })
                      }
                    >
                      사용 중지
                    </button>
                  )}
                  <button
                    type="button"
                    disabled={locked}
                    onClick={() => select()}
                  >
                    관리 닫기
                  </button>
                </>
              )}
            </form>
          </section>
        </>
      )}
      {notice && <p role="status">{notice}</p>}
      {error && (
        <aside role="alert">
          <p>{error}</p>
          {retry.current && !busy && (
            <button
              onClick={() => {
                const p = retry.current;
                if (p) void send("", {}, p);
              }}
            >
              같은 요청으로 다시 확인
            </button>
          )}
        </aside>
      )}
    </section>
  );
}
