// MES 화면 공통: 공통 훅(shared/hooks)에 MES 접두사를 붙이고, MES 전용 안내·버전 버튼을 둔다
import { Badge, EmptyState } from "../shared/components";
import { useApiLists, useApiSend } from "../shared/hooks";
export { fieldErrors, moduleOff } from "../shared/hooks";

export const MES = "/api/v1/mes";

export type Site = {
  id: number;
  siteCode: string;
  name: string;
  timezone: string;
};
export type Place = {
  id: number;
  siteId: number;
  parentLocationId: number | null;
  locationCode: string;
  name: string;
  kind: "building" | "zone" | "workcenter";
};
export type Equipment = {
  id: number;
  locationId: number;
  equipmentCode: string;
  name: string;
  equipmentType: string;
  isActive: boolean;
};

export function MesOrder() {
  return (
    <ol className="master-order" aria-label="기준정보 등록 순서">
      <li>사업장 → 공간 → 설비</li>
      <li>공정 (허용 설비 필요)</li>
      <li>품목 → 단위 환산</li>
      <li>공정 경로 · BOM (품목·공정 필요)</li>
    </ol>
  );
}

/** 수정 시 바뀐 값만 보낸다. */
export function changed(draft: object, current: object) {
  return Object.fromEntries(
    Object.entries(draft).filter(
      ([k, v]) =>
        JSON.stringify((current as Record<string, unknown>)[k]) !==
        JSON.stringify(v),
    ),
  );
}

export function ModuleOff() {
  return (
    <EmptyState
      reason="MES를 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다."
      to="/workspace"
      action="내 공간으로"
    />
  );
}

/** 여러 목록을 한 번에 불러온다. reload()로 다시 불러온다. */
export const useLists = <T extends unknown[]>(paths: string[]) =>
  useApiLists<T>(MES, paths);

/** 저장·삭제 요청. 성공하면 onDone(보통 목록 다시 불러오기)을 부른다. */
export const useSend = (onDone: () => void) => useApiSend(MES, onDone);

// ---- 버전(공정 경로·BOM): 초안 → 게시 → 폐기 ----
export type VersionStatus = "draft" | "published" | "retired";
const STATUS: Record<VersionStatus, [string, "normal" | "warning" | "issue"]> =
  {
    draft: ["초안", "warning"],
    published: ["게시", "normal"],
    retired: ["폐기", "issue"],
  };
export function StatusBadge({ status }: { status: VersionStatus }) {
  const [label, tone] = STATUS[status];
  return <Badge tone={tone}>{label}</Badge>;
}

/** 상태에 맞는 버전 작업 버튼. 초안: 게시·삭제 / 게시: 개정·폐기 / 폐기: 개정. */
export function versionButtons(
  row: { id: number; status: VersionStatus },
  base: string,
  send: ReturnType<typeof useSend>["send"],
  deleteButtons: ReturnType<typeof useSend>["deleteButtons"],
  revise: () => void,
) {
  const post = (action: string) =>
    void send(`${base}/${row.id}/${action}`, "POST");
  return (
    <>
      {row.status === "draft" && (
        <button
          type="button"
          className="link-button"
          onClick={() => post("publish")}
        >
          게시
        </button>
      )}
      {row.status !== "draft" && (
        <button type="button" className="link-button" onClick={revise}>
          개정
        </button>
      )}
      {row.status === "published" && (
        <button
          type="button"
          className="link-button"
          onClick={() => post("retire")}
        >
          폐기
        </button>
      )}
      {row.status === "draft" &&
        deleteButtons(`v:${row.id}`, `${base}/${row.id}`)}
    </>
  );
}
