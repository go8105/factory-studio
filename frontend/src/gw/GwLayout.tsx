import { useState } from "react";
import { SolutionLayout, type Screen } from "../shared/SolutionLayout";
import { useSession } from "../app/session";
import { RoleContext, useGet, type Page, type Person } from "./common";
export const gwScreens: Screen[] = [
  { path: "dashboard", id: "G-01", label: "업무 현황", group: "전자결재" },
  { path: "drafts", id: "G-02", label: "기안함", group: "전자결재" },
  { path: "pending", id: "G-03", label: "결재함", group: "전자결재" },
  { path: "documents", id: "G-04", label: "결재 기록", group: "전자결재" },
  { path: "board", id: "G-05", label: "공지·자유 게시판", group: "게시판" },
  { path: "routes", id: "G-06", label: "결재선 템플릿", group: "기준정보" },
  { path: "people", id: "G-07", label: "체험 담당자", group: "기준정보" },
  {
    path: "authority-rules",
    id: "G-08",
    label: "전결 규칙",
    group: "기준정보",
  },
  { path: "delegations", id: "G-09", label: "결재 위임", group: "전자결재" },
];
function Space() {
  const { session } = useSession();
  const key = `gw-role:${session?.workspaceId}:${session?.generationId}`;
  const [selected, setSelected] = useState(
    () => sessionStorage.getItem(key) ?? "",
  );
  const [busy, setBusy] = useState(false);
  const people = useGet<Page<Person>>("/people?limit=100");
  const valid = people.data?.rows.some((p) => p.id === selected && p.isActive)
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
        people: people.data?.rows ?? [],
        reload: people.reload,
        error: people.error,
        busy,
        setBusy,
      }}
    >
      <SolutionLayout
        name="GW"
        title="GW 그룹웨어"
        base="/gw"
        screens={gwScreens}
        others={["mes", "erp", "fems", "qms", "wms", "bems", "spc"]
          .map((k) => ({ to: "/" + k, label: k.toUpperCase() }))
          .concat({ to: "/home", label: "포털 홈" })}
      />
    </RoleContext.Provider>
  );
}
export function GwLayout() {
  const { session } = useSession();
  return <Space key={`${session?.workspaceId}:${session?.generationId}`} />;
}
