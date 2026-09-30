// P-01 진입
import { useRef, useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useSession } from "../app/session";
import { api, MutationKeys, type Session } from "../shared/api";
import { ErrorNotice, Field, Loading } from "../shared/components";
import { fieldErrors } from "../shared/hooks";
export function Entry() {
  const { session, setSession } = useSession();
  const navigate = useNavigate();
  const [login, setLogin] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [loginId, setLoginId] = useState("");
  const [password, setPassword] = useState("");
  const [nickname, setNickname] = useState("");
  const keys = useRef(new MutationKeys());
  const lastAttempt = useRef(false);
  if (session) return <Navigate to="/home" replace />;
  const nicknameError = fieldErrors(error).nickname;
  async function enter(member: boolean) {
    lastAttempt.current = member;
    setBusy(true);
    setError(undefined);
    const operation = JSON.stringify(
      member ? { loginId, password } : { nickname: nickname.trim() },
    );
    try {
      const response = await api<Session>(
        member ? "/sessions" : "/guest-sessions",
        {
          method: "POST",
          key: keys.current.get(operation),
          body: member ? { loginId, password } : { nickname: nickname.trim() },
        },
      );
      keys.current.complete(operation);
      setSession({ ...response.data, roles: response.data.roles ?? ["GUEST"] });
      setPassword("");
      navigate("/home");
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  function submit(e: FormEvent) {
    e.preventDefault();
    void enter(true);
  }
  return (
    <main className="entry">
      <div className="entry-top">
        <Link className="brand" to="/">
          Factory Studio<span>제조 업무 포트폴리오</span>
        </Link>
        <Link to="/help/portal/p-01" className="help-link">
          ? 진입 도움말
        </Link>
      </div>
      <div className="entry-body">
        <span className="eyebrow">MANUFACTURING SYSTEMS / 01</span>
        <h1>
          제조 현장의
          <br />
          올인원 시스템
        </h1>
        <p className="lead">
          MES · ERP · FEMS · QMS · WMS · BEMS · SPC를 각각 독립된 솔루션으로
          만들었습니다.
          <br />
          가입 없이 바로 둘러보세요.
        </p>
        <form
          className="guest-form"
          aria-label="가입 없이 둘러보기"
          onSubmit={(e) => {
            e.preventDefault();
            void enter(false);
          }}
        >
          <Field
            label="별칭"
            placeholder="실명 대신 별칭 (2~20자)"
            value={nickname}
            required
            minLength={2}
            maxLength={20}
            disabled={busy}
            error={lastAttempt.current ? undefined : nicknameError}
            onChange={(e) => setNickname(e.target.value)}
          />
          <button
            className="primary entry-action"
            type="submit"
            disabled={busy}
          >
            가입 없이 둘러보기 <span aria-hidden="true">→</span>
          </button>
        </form>
        <p className="muted">
          별칭은 접속 기록 확인용으로 90일 보관합니다. 실명·연락처는 적지
          마세요.
          <br />
          예시 데이터가 채워진 임시 공간이 생성됩니다.
          <br />
          게스트 공간은 생성일 다음 날 00:00(한국 시간)에 만료됩니다.
        </p>
        {busy && (
          <Loading delay={1000} label="예시 데이터를 준비하고 있습니다" />
        )}
        <ErrorNotice
          error={nicknameError ? undefined : error}
          retry={!busy ? () => void enter(lastAttempt.current) : undefined}
        />
        <button
          className="link-button"
          onClick={() => setLogin(!login)}
          disabled={busy}
          aria-expanded={login}
        >
          계정이 있다면 로그인
        </button>
        {login && (
          <form onSubmit={submit} className="login-form">
            <Field
              label="아이디"
              autoComplete="username"
              required
              value={loginId}
              onChange={(e) => setLoginId(e.target.value)}
              disabled={busy}
            />
            <Field
              label="비밀번호"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={busy}
            />
            <button type="submit" disabled={busy}>
              로그인
            </button>
          </form>
        )}
      </div>
      <footer className="entry-footer">
        <span>MES / 생산관리</span>
        <span>ERP / 경영관리</span>
        <span>FEMS / 에너지관리</span>
        <span>QMS / 품질관리</span>
        <span>WMS / 창고관리</span>
        <span>BEMS / 건물관리</span>
        <span>SPC / 공정관리</span>
      </footer>
    </main>
  );
}
