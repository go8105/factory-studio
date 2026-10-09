import { useState } from "react";
import { SolutionLayout } from "../shared/SolutionLayout";
import { gwScreens } from "../shared/menuCatalog";
import { useSession } from "../app/session";
import { RoleContext, useGet, type Person } from "./common";
export { gwScreens } from "../shared/menuCatalog";

function Space() {
  const { session } = useSession();
  const key = `gw-role:${session?.workspaceId}:${session?.generationId}`;
  const [selected, setSelected] = useState(
    () => sessionStorage.getItem(key) ?? "",
  );
  const [busy, setBusy] = useState(false);
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
      }}
    >
      <SolutionLayout
        name="GW"
        title="GW 그룹웨어"
        base="/gw"
        screens={gwScreens}
        others={["mes", "erp", "fems", "qms", "wms", "bems", "spc", "hr"]
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
