// P-06 내 공간
import { useEffect, useRef, useState } from "react";
import { useSession } from "../app/session";
import {
  api,
  ApiError,
  MutationKeys,
  type Module,
  type Workspace as WorkspaceData,
} from "../shared/api";
import { Badge, ErrorNotice, Loading } from "../shared/components";
import { WorkspaceFavorites } from "./WorkspaceFavorites";
import { solutions } from "./Home";
export function Workspace() {
  const { session, refresh, fail, busy, setBusy, setNavigationBlocked } =
    useSession();
  const [workspace, setWorkspace] = useState<WorkspaceData>();
  const [modules, setModules] = useState<Module[]>([]);
  const [error, setError] = useState<unknown>();
  const [confirm, setConfirm] = useState(false);
  const [done, setDone] = useState("");
  const [now, setNow] = useState(Date.now());
  const keys = useRef(new MutationKeys());
  const inFlight = useRef(false);
  const [reloadNeeded, setReloadNeeded] = useState(false);
  function showError(e: unknown) {
    setError(e);
    if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
  }
  const [uncertain, setUncertain] = useState<{ module?: Module } | null>(null);
  async function load() {
    const [w, m] = await Promise.all([
      api<WorkspaceData>("/workspace"),
      api<Module[]>("/workspace/modules"),
    ]);
    setWorkspace(w.data);
    setModules(m.data);
  }
  useEffect(() => {
    load().catch(showError);
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  async function reload() {
    setBusy(true);
    setError(undefined);
    try {
      await refresh();
      await load();
      setReloadNeeded(false);
    } catch (e) {
      setReloadNeeded(true);
      showError(e);
    } finally {
      setBusy(false);
    }
  }
  async function mutate(module?: Module) {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    if (!module) setNavigationBlocked(true);
    let keepNavigationBlocked = false;
    setError(undefined);
    setDone("");
    const operation = module
      ? `${module.moduleKey}:${!module.enabled}`
      : "reset";
    try {
      await api(
        module
          ? `/workspace/modules/${module.moduleKey}`
          : "/workspace/generations",
        {
          method: module ? "PATCH" : "POST",
          body: module ? { enabled: !module.enabled } : undefined,
          csrf: session?.csrfToken,
          key: keys.current.get(operation),
        },
      );
      keys.current.complete(operation);
      setUncertain(null);
      setConfirm(false);
      setDone(
        module
          ? "앱 사용 여부를 변경했습니다."
          : "새 예시 데이터 세대로 초기화했습니다.",
      );
      // 변경은 이미 성공했다. 후속 조회 실패는 GET만 재시도한다.
      try {
        await refresh();
        await load();
        setReloadNeeded(false);
      } catch (e) {
        setReloadNeeded(true);
        showError(e);
      }
    } catch (e) {
      if (e instanceof ApiError && (e.status === 0 || e.status >= 500)) {
        setUncertain({ module });
        keepNavigationBlocked = !module;
      } else {
        setUncertain(null);
      }
      showError(e);
    } finally {
      inFlight.current = false;
      if (!module) setNavigationBlocked(keepNavigationBlocked);
      setBusy(false);
    }
  }
  const expiresAt =
    workspace?.workspaceKind === "GUEST" ? workspace.expiresAt : null;
  const left = expiresAt
    ? Math.max(0, Math.ceil((Date.parse(expiresAt) - now) / 60000))
    : null;
  return (
    <>
      <WorkspaceFavorites
        modules={modules}
        disabled={busy || !!uncertain || reloadNeeded}
      />
      <ErrorNotice
        error={error}
        retry={
          !busy
            ? uncertain
              ? () => void mutate(uncertain.module)
              : () => void reload()
            : undefined
        }
      />
      {done && (
        <p role="status" className="notice">
          {done}
        </p>
      )}
      {!workspace ? (
        !error && <Loading />
      ) : (
        <>
          <section className="panel workspace-summary">
            <div>
              <Badge>
                {workspace.workspaceKind === "GUEST"
                  ? "게스트 임시 공간"
                  : "개인 공간"}
              </Badge>
              <h2>공간 {workspace.id}</h2>
              <p>
                활성 데이터 세대 {session?.generationId} · 설정 버전{" "}
                {workspace.configVersion}
              </p>
            </div>
            {expiresAt && (
              <div>
                <strong>남은 시간 {left}분</strong>
                <p>
                  만료 예정{" "}
                  {new Date(expiresAt).toLocaleString("ko-KR", {
                    timeZone: "Asia/Seoul",
                  })}{" "}
                  KST
                </p>
                <small>
                  게스트 공간의 만료 시각은 활동 여부와 관계없이 고정됩니다.
                </small>
              </div>
            )}
          </section>
          <section className="panel">
            <h2>앱 사용 여부</h2>
            <p>사용을 끈 앱은 런처에서 흐리게 표시됩니다.</p>
            <div className="toggle-list">
              {solutions.map((s) => {
                const m = modules.find((m) => m.moduleKey === s.key);
                return (
                  m && (
                    <div key={s.key}>
                      <div>
                        <strong>
                          {s.key.toUpperCase()} · {s.name}
                        </strong>
                        <p>{s.description}</p>
                      </div>
                      <button
                        role="switch"
                        aria-checked={m.enabled}
                        aria-label={`${s.key.toUpperCase()} 사용`}
                        disabled={busy || !!uncertain || reloadNeeded}
                        onClick={() => void mutate(m)}
                      >
                        {m.enabled ? "켜짐" : "꺼짐"}
                        <span className="toggle-track" aria-hidden="true" />
                      </button>
                    </div>
                  )
                );
              })}
            </div>
          </section>
          <section className="panel">
            <h2>예시 데이터 초기화</h2>
            <p>
              새로운 데이터 세대로 바꿉니다. 기존 데이터로 되돌릴 수 없으며 앱
              사용 설정은 유지됩니다.
            </p>
            {confirm ? (
              <div className="notice">
                <p id="reset-warning">
                  변경한 예시 데이터는 되돌릴 수 없습니다. 초기화하시겠습니까?
                </p>
                <div className="actions">
                  <button
                    aria-describedby="reset-warning"
                    disabled={busy || !!uncertain || reloadNeeded}
                    onClick={() => void mutate()}
                  >
                    초기화 확인
                  </button>
                  <button
                    className="secondary"
                    disabled={busy || !!uncertain || reloadNeeded}
                    onClick={() => setConfirm(false)}
                  >
                    취소
                  </button>
                </div>
              </div>
            ) : (
              <button
                className="secondary"
                disabled={busy || !!uncertain || reloadNeeded}
                onClick={() => setConfirm(true)}
              >
                예시 데이터 초기화
              </button>
            )}
            {busy && (
              <Loading label="변경 사항을 적용하고 있습니다. 이동하지 말아 주세요." />
            )}
          </section>
        </>
      )}
    </>
  );
}
