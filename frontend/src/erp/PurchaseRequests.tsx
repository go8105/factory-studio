// E-22 구매 요청 (DSN-11 F21)
import { DocumentScreen, type Doc, type Row } from "./document";
type Request = Doc & {
  requestNo: string;
  requestedOn: string;
  departmentCode: string | null;
  employeeCode: string | null;
  source: string;
  sourceRef: string | null;
};
const today = () => new Date().toISOString().slice(0, 10);
function Picker({
  label,
  rows,
  value,
  onChange,
}: {
  label: string;
  rows: Row[];
  value: unknown;
  onChange: (id: number | undefined) => void;
}) {
  return (
    <label>
      {label}
      <select
        value={String(value ?? "")}
        onChange={(e) =>
          onChange(e.target.value ? Number(e.target.value) : undefined)
        }
      >
        <option value="">지정 안 함</option>
        {rows.map((r) => (
          <option key={r.id} value={r.id}>
            {r.code} {r.name}
          </option>
        ))}
      </select>
    </label>
  );
}
export function PurchaseRequests() {
  return (
    <DocumentScreen<Request>
      id="E-22"
      title="구매 요청"
      path="/purchase-requests"
      note="필요한 것을 먼저 올리고, 확정한 요청만 발주(E-23)로 끌어갑니다. 요청에는 금액이 없습니다 — 단가는 발주에서 정합니다. 발주로 넘어간 요청은 취소할 수 없습니다."
      blank={{ requestedOn: today(), source: "MANUAL" }}
      extraPaths={["/departments?limit=200", "/employees?limit=200"]}
      columns={() => [
        { key: "requestNo", label: "요청 번호" },
        { key: "requestedOn", label: "요청일" },
        {
          key: "departmentCode",
          label: "부서",
          render: (r) => r.departmentCode ?? "—",
        },
        {
          key: "employeeCode",
          label: "담당자",
          render: (r) => r.employeeCode ?? "—",
        },
        {
          key: "sourceRef",
          label: "원천",
          render: (r) =>
            r.source === "MANUAL" ? "수동" : `${r.source} ${r.sourceRef}`,
        },
      ]}
      form={(draft, set, lists, errors) => (
        <>
          <label>
            요청일
            <input
              type="date"
              value={String(draft.requestedOn ?? "")}
              onChange={(e) => set({ requestedOn: e.target.value })}
            />
          </label>
          {errors.requestedOn && (
            <small role="alert">{errors.requestedOn}</small>
          )}
          <Picker
            label="부서"
            rows={lists.extras[0] ?? []}
            value={draft.departmentId}
            onChange={(id) => set({ departmentId: id })}
          />
          <Picker
            label="담당자"
            rows={lists.extras[1] ?? []}
            value={draft.employeeId}
            onChange={(id) => set({ employeeId: id })}
          />
          <p className="muted">
            부서·담당자는 E-19에서 등록한 값입니다. 비워 두어도 됩니다.
          </p>
        </>
      )}
      lineItems={(items) =>
        items.filter((i) => !["finished", "semi_finished"].includes(i.itemType))
      }
    />
  );
}
