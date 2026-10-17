import { MasterScreen, CODE_PATTERN, type MasterSpec } from "../shared/master";
import { useContext } from "react";
import { ApiError } from "../shared/api";
import {
  CompanyContext,
  documentKinds,
  labels,
  useRole,
  useSend,
} from "./common";
type Rule = {
  id: number;
  code: string;
  documentKind: string;
  currency: string;
  amountFrom: string;
  amountTo: string | null;
  finalSeq: number;
  effectiveFrom: string;
  effectiveTo: string | null;
  isActive: boolean;
  version: number;
};
type Draft = Omit<Rule, "id" | "version"> & Record<string, unknown>;
const spec: MasterSpec<Rule, Draft> = {
  id: "G-08",
  title: "전결 규칙",
  help: "gw/g-08",
  base: "/api/v1/gw/authority-rules",
  blank: {
    code: "",
    documentKind: "GENERAL",
    currency: "KRW",
    amountFrom: "0",
    amountTo: null,
    finalSeq: 1,
    effectiveFrom: new Date()
      .toLocaleDateString("sv-SE", { timeZone: "Asia/Seoul" })
      .slice(0, 7),
    effectiveTo: null,
    isActive: true,
  },
  updateBody: (changes, row) => ({ ...changes, expectedVersion: row.version }),
  intro: (
    <p>
      금액은 하한 이상·상한 미만, 적용 월은 시작·종료 월을 포함합니다. 같은
      종류·통화·기간의 금액 구간은 겹칠 수 없습니다. 상신에 사용한 규칙은 비활성
      처리만 할 수 있습니다.
    </p>
  ),
  columns: [
    { key: "code", label: "코드" },
    {
      key: "documentKind",
      label: "종류",
      render: (r) => labels[r.documentKind],
    },
    { key: "currency", label: "통화" },
    { key: "amountFrom", label: "하한 (포함)" },
    {
      key: "amountTo",
      label: "상한 (미포함)",
      render: (r) => r.amountTo ?? "없음",
    },
    { key: "finalSeq", label: "최종 단계" },
    { key: "effectiveFrom", label: "시작 월" },
    { key: "effectiveTo", label: "종료 월" },
    {
      key: "isActive",
      label: "사용",
      render: (r) => (r.isActive ? "사용" : "비활성"),
    },
  ],
  fields: [
    {
      kind: "text",
      key: "code",
      label: "규칙 코드",
      required: true,
      pattern: CODE_PATTERN,
      upper: true,
      maxLength: 30,
    },
    {
      kind: "select",
      key: "documentKind",
      label: "문서 종류",
      options: Object.fromEntries(documentKinds.map((k) => [k, labels[k]])),
    },
    {
      kind: "text",
      key: "currency",
      label: "통화",
      required: true,
      pattern: "[A-Z]{3}",
      upper: true,
      maxLength: 3,
    },
    {
      kind: "text",
      key: "amountFrom",
      label: "금액 하한 (포함)",
      required: true,
    },
    {
      kind: "number",
      key: "finalSeq",
      label: "최종 결재 단계",
      min: 1,
      max: 3,
      required: true,
    },
    { kind: "check", key: "isActive", label: "사용" },
  ],
  extra: (d, set) => (
    <>
      <label>
        금액 상한 (미포함, 비우면 제한 없음)
        <input
          aria-label="금액 상한"
          value={d.amountTo ?? ""}
          onChange={(e) => set({ amountTo: e.target.value || null })}
        />
      </label>
      <label>
        시작 월
        <input
          type="month"
          required
          aria-label="시작 월"
          value={d.effectiveFrom}
          onChange={(e) => set({ effectiveFrom: e.target.value })}
        />
      </label>
      <label>
        종료 월 (포함, 선택)
        <input
          type="month"
          aria-label="종료 월"
          value={d.effectiveTo ?? ""}
          onChange={(e) => set({ effectiveTo: e.target.value || null })}
        />
      </label>
    </>
  ),
  labels: {
    create: "전결 규칙 등록",
    caption: "전결 규칙",
    emptyReason:
      "등록된 전결 규칙이 없습니다. 규칙이 없으면 모든 결재 단계를 진행합니다.",
    editTitle: (r) => `${r.code} 수정`,
    deleted: (r) => `${r.code} 삭제`,
    moduleOff: "GW가 꺼져 있습니다.",
  },
};
export function Authority() {
  const role = useRole();
  const scope = useContext(CompanyContext);
  const req = useSend();
  const companySpec: MasterSpec<Rule, Draft> = {
    ...spec,
    requestQuery: new URLSearchParams({
      companyId: role.companyId ?? "",
    }).toString(),
    readOnly: !role.roles?.includes("POLICY_ADMIN"),
    deleteBody: (row) => ({ expectedVersion: row.version }),
    onLoadError: (e) => {
      if (e instanceof ApiError && [403, 404].includes(e.status))
        scope.invalidate?.(e);
    },
    transport: {
      ...req,
      send: <T,>(path: string, method: string, body?: unknown) =>
        req.send<T>("/authority-rules" + path, method, body),
    },
    fields: spec.fields.map((f) =>
      f.key === "documentKind" && f.kind === "select"
        ? { ...f, options: { GENERAL: labels.GENERAL } }
        : f,
    ),
  };
  return (
    <MasterScreen spec={role.companyId !== undefined ? companySpec : spec} />
  );
}
