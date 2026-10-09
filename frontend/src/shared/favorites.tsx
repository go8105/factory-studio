import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useLocation } from "react-router-dom";
import { useSession } from "../app/session";
import { api, ApiError, MutationKeys } from "./api";
import { menuByKey, menuCatalog, menuSolutions } from "./menuCatalog";

export type Preferences = {
  menuIds: string[];
  sidebarMode: "all" | "favorites";
  version: number;
};
type State = {
  data?: Preferences;
  loading: boolean;
  pending: boolean;
  uncertain: boolean;
  error?: unknown;
  recent: string[];
  save: (
    menuIds: string[],
    sidebarMode: Preferences["sidebarMode"],
  ) => Promise<boolean>;
  reload: () => Promise<Preferences | undefined>;
};
const Context = createContext<State>({
  loading: false,
  pending: false,
  uncertain: false,
  recent: [],
  save: async () => false,
  reload: async () => undefined,
});
export const useFavorites = () => useContext(Context);

function recentMenus(key: string) {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(key) ?? "[]");
    return Array.isArray(value)
      ? [
          ...new Set(
            value.filter(
              (v): v is string => typeof v === "string" && menuByKey.has(v),
            ),
          ),
        ].slice(0, 6)
      : [];
  } catch {
    return [];
  }
}
function preferences(value: Preferences): Preferences {
  if (
    !value ||
    !Array.isArray(value.menuIds) ||
    !["all", "favorites"].includes(value.sidebarMode) ||
    !Number.isInteger(value.version) ||
    value.version < 1
  )
    throw new Error("메뉴 구성을 불러오지 못했습니다.");
  return {
    ...value,
    menuIds: [...new Set(value.menuIds.filter((key) => menuByKey.has(key)))],
  };
}

function SpaceFavorites({ children }: { children: ReactNode }) {
  const { session, fail, setBusy, setNavigationBlocked } = useSession();
  const location = useLocation();
  const needsPreferences =
    location.pathname === "/workspace" ||
    menuSolutions.some(
      (solution) =>
        location.pathname === `/${solution.key}` ||
        location.pathname.startsWith(`/${solution.key}/`),
    );
  const [data, setData] = useState<Preferences>();
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>();
  const [uncertain, setUncertain] = useState(false);
  const storageKey = `fs.recentMenus:v1:${session?.actorKind}:${session?.workspaceId}`;
  const [recent, setRecent] = useState(() => recentMenus(storageKey));
  const inFlight = useRef(false);
  const ownsNavigationBlock = useRef(false);
  const retryBody = useRef<
    | {
        menuIds: string[];
        sidebarMode: Preferences["sidebarMode"];
        expectedVersion: number;
      }
    | undefined
  >(undefined);
  const keys = useRef(new MutationKeys());

  function showError(e: unknown) {
    setError(e);
    if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
  }
  async function reload() {
    if (inFlight.current) return;
    setLoading(true);
    setError(undefined);
    try {
      const value = preferences(
        (await api<Preferences>("/workspace/menus")).data,
      );
      setData(value);
      // A GET also resolves an uncertain write: it shows the actual server configuration.
      setUncertain(false);
      retryBody.current = undefined;
      if (ownsNavigationBlock.current) setNavigationBlocked(false);
      ownsNavigationBlock.current = false;
      return value;
    } catch (e) {
      showError(e);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    if (!needsPreferences) {
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    api<Preferences>("/workspace/menus", { signal: controller.signal })
      .then((r) => {
        if (!controller.signal.aborted) {
          setData(preferences(r.data));
          setError(undefined);
        }
      })
      .catch((e) => {
        if (!controller.signal.aborted) showError(e);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [session?.generationId, needsPreferences]);

  useEffect(() => {
    const menu = menuCatalog.find(
      (m) =>
        location.pathname === m.to || location.pathname.startsWith(`${m.to}/`),
    );
    if (!menu) return;
    setRecent((old) => {
      const next = [menu.key, ...old.filter((key) => key !== menu.key)].slice(
        0,
        6,
      );
      try {
        localStorage.setItem(storageKey, JSON.stringify(next));
      } catch {
        /* current session still works */
      }
      return next;
    });
  }, [location.pathname, storageKey]);

  async function save(
    menuIds: string[],
    sidebarMode: Preferences["sidebarMode"],
  ) {
    if (!data || inFlight.current || loading) return false;
    const body = retryBody.current ?? {
      menuIds,
      sidebarMode,
      expectedVersion: data.version,
    };
    const operation = JSON.stringify(body);
    inFlight.current = true;
    ownsNavigationBlock.current = true;
    setPending(true);
    setBusy(true);
    setNavigationBlocked(true);
    setError(undefined);
    let unresolved = false;
    try {
      const result = await api<Preferences>("/workspace/menus", {
        method: "PUT",
        body,
        csrf: session?.csrfToken,
        key: keys.current.get(operation),
      });
      setData(preferences(result.data));
      keys.current.complete(operation);
      retryBody.current = undefined;
      setUncertain(false);
      return true;
    } catch (e) {
      unresolved =
        !(e instanceof ApiError) || e.status === 0 || e.status >= 500;
      if (unresolved) retryBody.current = body;
      else {
        keys.current.complete(operation);
        retryBody.current = undefined;
      }
      setUncertain(unresolved);
      showError(e);
      return false;
    } finally {
      inFlight.current = false;
      setPending(false);
      setBusy(false);
      setNavigationBlocked(unresolved);
      ownsNavigationBlock.current = unresolved;
    }
  }
  return (
    <Context.Provider
      value={{ data, loading, pending, uncertain, error, recent, save, reload }}
    >
      {children}
    </Context.Provider>
  );
}

export function FavoritesProvider({ children }: { children: ReactNode }) {
  const { session } = useSession();
  return session ? (
    <SpaceFavorites key={`${session.actorKind}:${session.workspaceId}`}>
      {children}
    </SpaceFavorites>
  ) : (
    children
  );
}
