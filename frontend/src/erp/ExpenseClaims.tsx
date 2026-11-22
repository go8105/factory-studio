// E-29 지출결의서 (DSN-11 F46)
import { Field } from "../shared/components";
import { won } from "./common";
import { DocumentScreen, type Doc, type DraftLine, type Row } from "./document";

type Claim = Doc & {
  claimNo: string;
  claimedOn: string;
  employeeCode: string;
  employeeName: string;
  departmentCode: string;
  payMethod: "BANK" | "CARD" | "CASH";
  totalAmount: string;
};
const PAY = { BANK: "계좌 이체", CARD: "법인카드", CASH: "현금" };
const today = () => new Date().toISOString().slice(0, 10);
function Picker({
  label,
  rows,
  value,
  onChange,
  required,
}: {
  label: string;
  rows: Row[];
  value: unknown;
  onChange: (id: number | undefined) => void;
  required?: boolean;
}) {
  return (
    <label>
      {label}
      <select
        required={required}
        value={String(value ?? "")}
        onChange={(e) =>
          onChange(e.target.value ? Number(e.target.value) : undefined)
        }
      >
        <option value="">선택하세요</option>
        {rows.map((r) => (
          <option key={r.id} value={r.id}>
            {r.code} {r.name}
          </option>
        ))}
      </select>
    </label>
  );
}
export function ExpenseClaims() {
  return (
    <DocumentScreen<Claim>
      id="E-29"
      title="지출결의서"
      path="/expense-claims"
      note="쓴 돈을 비용 계정별로 적고 확정하면 비용 전표가 함께 생깁니다. 차변은 명세가 고른 비용 계정이고, 대변은 지급 방법이 정합니다(계좌·현금은 보통예금, 카드는 미지급금). GW 결재 상태는 읽기만 하고 확정을 막지 않습니다."
      blank={{ claimedOn: today(), payMethod: "BANK" }}
      extraPaths={[
        "/employees?limit=200",
        "/departments?limit=200",
        "/accounts?limit=200",
      ]}
      columns={() => [
        { key: "claimNo", label: "결의 번호" },
        { key: "claimedOn", label: "청구일" },
        {
          key: "employeeCode",
          label: "청구자",
          render: (c) => `${c.employeeCode} ${c.employeeName}`,
        },
        { key: "departmentCode", label: "부서" },
        {
          key: "payMethod",
          label: "지급 방법",
          render: (c) => PAY[c.payMethod],
        },
        {
          key: "totalAmount",
          label: "합계",
          render: (c) => won(c.totalAmount),
        },
      ]}
      lineColumns={[
        { key: "lineNo", label: "순서", render: (l) => l.lineNo },
        {
          key: "itemCode",
          label: "비용 계정",
          render: (l) =>
            `${String(l.accountCode ?? "")} ${String(l.accountName ?? "")}`,
        },
        {
          key: "quantity",
          label: "금액",
          render: (l) => won(String(l.amount ?? "0")),
        },
      ]}
      lineEditor={(lines, setLines, lists, errors) => (
        <>
          {lines.map((line, index) => (
            <div className="field-row" key={index}>
              <select
                aria-label={`${index + 1}번째 비용 계정`}
                value={String(line.accountId ?? "")}
                onChange={(e) =>
                  setLines(
                    lines.map((l, i) =>
                      i === index
                        ? { ...l, accountId: Number(e.target.value) }
                        : l,
                    ),
                  )
                }
              >
                <option value="">계정 선택</option>
                {(lists.extras[2] ?? [])
                  .filter((a) =>
                    ["EXPENSE", "MFG_COST"].includes(String(a.accountClass)),
                  )
                  .map((a) => (
                    <option key={a.id} value={a.id}>
                      {String(a.accountCode)} {String(a.accountName)}
                    </option>
                  ))}
              </select>
              <Field
                label={`${index + 1}번째 금액`}
                value={String(line.amount ?? "")}
                onChange={(e) =>
                  setLines(
                    lines.map((l, i) =>
                      i === index ? { ...l, amount: e.target.value } : l,
                    ),
                  )
                }
              />
              <button
                type="button"
                className="link-button"
                onClick={() => setLines(lines.filter((_, i) => i !== index))}
              >
                줄 삭제
              </button>
            </div>
          ))}
          {errors.lines && <small role="alert">{errors.lines}</small>}
          <button
            type="button"
            onClick={() =>
              setLines([
                ...lines,
                {
                  itemId: 0,
                  quantity: "",
                  accountId: 0,
                  amount: "",
                } as DraftLine,
              ])
            }
          >
            줄 추가
          </button>
        </>
      )}
      form={(draft, set, lists, errors) => (
        <>
          <label>
            청구일
            <input
              type="date"
              value={String(draft.claimedOn ?? "")}
              onChange={(e) => set({ claimedOn: e.target.value })}
            />
          </label>
          <Picker
            label="청구자"
            required
            rows={lists.extras[0] ?? []}
            value={draft.employeeId}
            onChange={(id) => set({ employeeId: id })}
          />
          {errors.employeeId && <small role="alert">{errors.employeeId}</small>}
          <Picker
            label="부서"
            required
            rows={lists.extras[1] ?? []}
            value={draft.departmentId}
            onChange={(id) => set({ departmentId: id })}
          />
          {errors.departmentId && (
            <small role="alert">{errors.departmentId}</small>
          )}
          <label>
            지급 방법
            <select
              value={String(draft.payMethod ?? "BANK")}
              onChange={(e) => set({ payMethod: e.target.value })}
            >
              <option value="BANK">계좌 이체</option>
              <option value="CARD">법인카드</option>
              <option value="CASH">현금</option>
            </select>
          </label>
        </>
      )}
    />
  );
}
