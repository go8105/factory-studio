import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { api, ApiError, type Session } from "../shared/api";
import { ErrorNotice, Loading, SessionExpired } from "../shared/components";
import { useLocation } from "react-router-dom";
type State = {
  session: Session | null;
  refresh: () => Promise<void>;
  setSession: (value: Session | null) => void;
  fail: (error: unknown) => void;
  navigationBlocked: boolean;
  setNavigationBlocked: (value: boolean) => void;
  busy: boolean;
  setBusy: (value: boolean) => void;
};
const SessionContext = createContext<State | null>(null);
export function useSession() {
  const value = useContext(SessionContext);
  if (!value) throw new Error("SessionProvider required");
  return value;
}
export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>();
  const [expired, setExpired] = useState<number>();
  const [busy, setBusy] = useState(false);
  const [navigationBlocked, setNavigationBlocked] = useState(false);
  useEffect(() => {
    if (!busy && !navigationBlocked) return;
    const preventUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", preventUnload);
    return () => window.removeEventListener("beforeunload", preventUnload);
  }, [busy, navigationBlocked]);
  const location = useLocation();
  const initial = useRef(location.pathname);
  function fail(e: unknown) {
    if (e instanceof ApiError && [401, 410].includes(e.status)) {
      setSession(null);
      setBusy(false);
      setNavigationBlocked(false);
      setExpired(e.status);
    } else setError(e);
  }
  async function refresh() {
    const response = await api<Session>("/sessions/current");
    setSession(response.data);
    setExpired(undefined);
    setError(undefined);
  }
  useEffect(() => {
    let active = true;
    api<Session>("/sessions/current")
      .then((r) => {
        if (active) setSession(r.data);
      })
      .catch((e) => {
        if (e instanceof ApiError && e.error.code === "RECOVERY_ONLY") return;
        if (
          active &&
          (!(e instanceof ApiError) ||
            ![401, 410].includes(e.status) ||
            !["/", "/help"].some((p) => initial.current === p))
        )
          fail(e);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);
  if (loading)
    return (
      <main>
        <Loading label="세션을 확인하고 있습니다" />
      </main>
    );
  const isPublic =
    location.pathname === "/" ||
    location.pathname === "/account/recovery" ||
    location.pathname.startsWith("/help");
  return (
    <SessionContext.Provider
      value={{
        session,
        refresh,
        setSession: (value) => {
          setSession(value);
          setExpired(undefined);
          setError(undefined);
        },
        fail,
        busy,
        setBusy,
        navigationBlocked,
        setNavigationBlocked,
      }}
    >
      {error ? (
        <main>
          <ErrorNotice
            error={error}
            retry={() => {
              setError(undefined);
              refresh().catch(fail);
            }}
          />
        </main>
      ) : expired && !isPublic ? (
        <main>
          <SessionExpired workspace={expired === 410} />
        </main>
      ) : (
        children
      )}
    </SessionContext.Provider>
  );
}
