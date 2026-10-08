// P-01 진입
import { useRef, useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useSession } from "../app/session";
import { api, MutationKeys, type Session } from "../shared/api";
import { ErrorNotice, Field, Loading } from "../shared/components";
import { fieldErrors } from "../shared/hooks";
import "./Entry.css";
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
      <div className="entry-layout">
        <div className="entry-body">
          <h1>
            제조 업무를 살펴보고,
            <br />
            직접 설계해 보세요.
          </h1>
          <p className="lead">
            독립된 제조 솔루션의 업무 흐름부터
            <br />
            CAD·CAM과 3D 공장 체험까지.
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
        <aside className="entry-product" aria-label="체험할 수 있는 기능">
          <figure>
            <img
              src="/images/nc-workspace.jpg"
              alt="합성 NC 경로와 예상 에너지 비교 화면"
              width="1440"
              height="900"
            />
            <figcaption>NC 경로 검토 · 합성 예제 · 예상 소비 모델</figcaption>
          </figure>
          <article>
            <h2>제조 업무 흐름</h2>
            <p>
              생산·경영·에너지 등 각 솔루션의 업무 화면과 설계 근거를
              확인합니다.
            </p>
          </article>
          <article>
            <h2>CAD·CAM 작업실</h2>
            <p>
              스케치와 3D 부품을 편집하고, NC 경로·시간·예상 소비를 비교합니다.
            </p>
            <Link to="/help/portal/cad-cam">설계·가공 사용법</Link>
          </article>
          <article>
            <h2>3D 공장</h2>
            <p>제조 공간을 탐색하고 CNC·검사 공정의 합성 시연을 살펴봅니다.</p>
            <Link to="/help/portal/factory">공장 체험 안내</Link>
          </article>
        </aside>
      </div>
      <footer className="entry-footer">
        <span>MES / 생산관리</span>
        <span>ERP / 경영관리</span>
        <span>FEMS / 에너지관리</span>
        <span>QMS / 품질관리</span>
        <span>WMS / 창고관리</span>
        <span>BEMS / 건물관리</span>
        <span>SPC / 공정관리</span>
        <span>GW / 그룹웨어</span>
        <span>HR / 인사·급여</span>
      </footer>
    </main>
  );
}
