import {
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { SolutionLayout } from "../shared/SolutionLayout";
import { ErrorNotice, Loading } from "../shared/components";
import { gwScreens } from "../shared/menuCatalog";
import { useSession } from "../app/session";
import {
  CompanyContext,
  RoleContext,
  useGet,
  useRole,
  type Person,
} from "./common";
import { CompanyStart, type CompanyMe } from "./Company";
export { gwScreens } from "../shared/menuCatalog";

function SpaceChoice() {
  const { session } = useSession();
  const role = useRole();
  const companies = useGet<{ id: number; name: string }[]>(
    session?.actorKind === "MEMBER" ? "/companies" : null,
  );
  return (
    <section className="gw-role" aria-label="GW 사용 공간">
      <strong>
        {role.companyId ? (role.companyName ?? "회사 공간") : "개인 체험"}
      </strong>
      {role.companyId && <p>{role.personName ?? "연결된 직원"} · 회사 GW</p>}
      <details>
        <summary>사용 공간 선택</summary>
        <nav
          className="gw-space-options"
          onClick={(e) => {
            if (role.busy || role.uncertain) {
              e.preventDefault();
              e.stopPropagation();
            }
          }}
        >
          <Link
            to="/gw/dashboard"
            aria-current={role.companyId === undefined ? "page" : undefined}
          >
            개인 체험
          </Link>
          {companies.data?.map((c) => (
            <Link
              key={c.id}
              to={`/gw/dashboard?companyId=${c.id}`}
              aria-current={
                String(c.id) === role.companyId ? "page" : undefined
              }
            >
              {c.name}
            </Link>
          ))}
        </nav>
      </details>
      <ErrorNotice error={companies.error} />
      {role.uncertain && (
        <p role="alert">
          응답을 확인하지 못한 요청이 있습니다. 같은 입력으로 다시 확인한 뒤
          공간을 변경하세요.
        </p>
      )}
    </section>
  );
}

function Layout({ content }: { content?: ReactNode }) {
  const role = useRole();
  const location = useLocation();
  return (
    <SolutionLayout
      name="GW"
      title="GW 그룹웨어"
      base="/gw"
      screens={gwScreens}
      screenLabels={
        role.companyId !== undefined
          ? { "gw:people": "회사 직원·권한" }
          : undefined
      }
      linkQuery={
        role.companyId !== undefined
          ? new URLSearchParams({ companyId: role.companyId }).toString()
          : undefined
      }
      beforeContent={
        <>
          <SpaceChoice />
          {role.companyId !== undefined && (
            <nav className="gw-company-navigation" aria-label="회사 운영 안내">
              <Link to="/account/security">내 계정 보안</Link>
              {role.roles?.some(
                (r) => r === "SECURITY_ADMIN" || r === "AUDITOR",
              ) && (
                <>
                  {" "}
                  ·{" "}
                  <Link
                    aria-current={
                      location.pathname === "/gw/operations"
                        ? "page"
                        : undefined
                    }
                    to={
                      "/gw/operations?companyId=" +
                      encodeURIComponent(role.companyId)
                    }
                  >
                    운영 준비
                  </Link>
                </>
              )}
            </nav>
          )}
        </>
      }
      content={content}
      others={["mes", "erp", "fems", "qms", "wms", "bems", "spc", "hr"]
        .map((k) => ({ to: "/" + k, label: k.toUpperCase() }))
        .concat([
          { to: "/work-os", label: "Factory Flow" },
          { to: "/hr/work", label: "내 근무 · 출퇴근" },
          { to: "/hr/work-demo", label: "근무 체험" },
          { to: "/home", label: "포털 홈" },
        ])}
    />
  );
}

function PersonalSpace() {
  const { session } = useSession();
  const key = `gw-role:${session?.workspaceId}:${session?.generationId}`;
  const [selected, setSelected] = useState(
    () => sessionStorage.getItem(key) ?? "",
  );
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const people = useGet<Person[]>("/people-options");
  const valid = people.data?.some((p) => p.id === selected && p.isActive)
    ? selected
    : "";
  return (
    <RoleContext.Provider
      value={{
        person: valid,
        setPerson: (p) => {
          setSelected(p);
          sessionStorage.setItem(key, p);
        },
        people: people.data ?? [],
        reload: people.reload,
        error: people.error,
        busy,
        setBusy,
        uncertain,
        setUncertain,
      }}
    >
      <Layout />
    </RoleContext.Provider>
  );
}

function CompanySpace({
  issue,
  retry,
  authorizationChanged,
}: {
  issue: unknown;
  retry: () => void;
  authorizationChanged: () => void;
}) {
  const scope = useContext(CompanyContext);
  const me = useGet<CompanyMe>("/me", true);
  const previousAuthorization = useRef<number | undefined>(undefined);
  const changed =
    me.data !== undefined &&
    previousAuthorization.current !== undefined &&
    previousAuthorization.current !== me.data.authzVersion;
  useLayoutEffect(() => {
    if (!me.data) return;
    previousAuthorization.current = me.data.authzVersion;
    if (changed) authorizationChanged();
  }, [me.data, changed, authorizationChanged]);
  const latestReload = useRef(me.reload);
  latestReload.current = me.reload;
  useEffect(() => {
    const refresh = () => latestReload.current();
    const timer = window.setInterval(refresh, 15000);
    window.addEventListener("focus", refresh);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", refresh);
    };
  }, []);
  const [search, setSearch] = useState("");
  const active =
    me.data?.bindingStatus === "ACTIVE" && me.data.person?.isActive;
  const people = useGet<Person[]>(
    active && !issue && me.data?.businessReady
      ? `/people-options?limit=100&search=${encodeURIComponent(search)}`
      : null,
  );
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const p = me.data?.person;
  let content;
  if (changed) content = <Loading label="현재 권한을 다시 확인하고 있습니다" />;
  else if (me.error)
    content = <ErrorNotice error={me.error} retry={me.reload} />;
  else if (!me.data) content = <Loading />;
  else if (issue)
    content = (
      <section className="card">
        <ErrorNotice error={issue} />
        <p>
          원문과 선택 상태를 비웠습니다. 현재 권한으로 다른 메뉴를 열거나 다시
          확인하세요.
        </p>
        <button onClick={retry}>권한과 연결 다시 확인</button>
      </section>
    );
  else if (!active || me.data.setupRequired)
    content = <CompanyStart me={me.data} reload={me.reload} />;
  else if (!me.data.businessReady)
    content = (
      <p role="status">
        회사 업무 연결을 검증 중입니다. 개인 체험을 이용할 수 있습니다.
      </p>
    );
  return (
    <RoleContext.Provider
      key={`${scope.companyId}:${scope.epoch}:${me.data?.authzVersion ?? 0}`}
      value={{
        person: active ? (p?.id ?? "") : "",
        setPerson: () => {},
        people: people.data ?? [],
        reload: () => {
          me.reload();
          people.reload();
        },
        companyId: scope.companyId,
        companyName: me.data?.company.name,
        personName: p?.name,
        organizationUnitId: p?.organizationUnitId,
        roles: me.data?.roles ?? [],
        error: people.error,
        busy,
        setBusy,
        uncertain,
        setUncertain,
        peopleSearch: search,
        setPeopleSearch: setSearch,
      }}
    >
      <Layout content={content} />
    </RoleContext.Provider>
  );
}

function CompanyRoot({ companyId }: { companyId: string }) {
  const [epoch, setEpoch] = useState(0);
  const [issue, setIssue] = useState<unknown>();
  const location = useLocation();
  const navigate = useNavigate();
  const currentLocation = useRef(location);
  currentLocation.current = location;
  const clearSelection = useCallback(() => {
    const current = currentLocation.current;
    const query = new URLSearchParams(current.search);
    if (!query.has("open")) return;
    query.delete("open");
    navigate(
      {
        pathname: current.pathname,
        search: query.toString(),
        hash: current.hash,
      },
      { replace: true, state: current.state },
    );
  }, [navigate]);
  const invalidate = useCallback(
    (error: unknown) => {
      clearSelection();
      setIssue(error);
      setEpoch((v) => v + 1);
    },
    [clearSelection],
  );
  const authorizationChanged = useCallback(() => {
    clearSelection();
    setEpoch((v) => v + 1);
  }, [clearSelection]);
  useEffect(() => setIssue(undefined), [location.pathname]);
  return (
    <CompanyContext.Provider value={{ companyId, epoch, invalidate }}>
      <CompanySpace
        key={epoch}
        issue={issue}
        authorizationChanged={authorizationChanged}
        retry={() => {
          setIssue(undefined);
          setEpoch((v) => v + 1);
        }}
      />
    </CompanyContext.Provider>
  );
}

export function GwLayout() {
  const { session } = useSession();
  const location = useLocation();
  const params = new URLSearchParams(location.search);
  const key = `${session?.workspaceId}:${session?.generationId}`;
  return params.has("companyId") ? (
    <CompanyRoot
      key={key + ":" + params.get("companyId")}
      companyId={
        params.getAll("companyId").length === 1
          ? (params.get("companyId") ?? "")
          : ""
      }
    />
  ) : (
    <PersonalSpace key={key} />
  );
}
