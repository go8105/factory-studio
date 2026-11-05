// F-23 고지서 대조 — 실제 청구 금액과 입력 시점의 산정 금액을 견준다 (DSN-15 F42)
// 회계 처리는 ERP 매입이다. 여기는 산정이 맞았는지만 본다.
import { useState } from "react";
import {
  Badge,
  ErrorNotice,
  Field,
  Loading,
  PageTitle,
} from "../shared/components";
import { fieldErrors, useApiLists, useApiSend } from "../shared/hooks";

type Bill = {
  id: number;
  sourceCode: string;
  sourceName: string;
  billMonth: string;
  billedQty: string;
  billedAmount: string;
  calculatedAmount: string;
  difference: string;
  differenceRate: string | null;
  note: string | null;
};
type Source = {
  id: number;
  sourceCode: string;
  name: string;
  isBillable: boolean;
  measureUnit: string;
};
type Created = Bill & { coverage?: { days: number; partial: boolean } };

const EMPTY = {
  energySourceId: "",
  billMonth: "",
  billedQty: "",
  billedAmount: "",
  note: "",
};
const won = (v: string) =>
  `${Number(v).toLocaleString("ko-KR", { maximumFractionDigits: 0 })}원`;

export function UtilityBills() {
  const lists = useApiLists<[Bill[], Source[]]>("/api/v1/fems", [
    "/utility-bills",
    "/energy-sources",
  ]);
  const { send, pending, error } = useApiSend("/api/v1/fems", lists.reload);
  const [draft, setDraft] = useState(EMPTY);
  const [done, setDone] = useState<string>();
  const [bills, sources] = lists.data ?? [];
  const billable = (sources ?? []).filter((s) => s.isBillable);
  const errors = fieldErrors(error);

  async function save() {
    const r = await send<Created>("/utility-bills", "POST", {
      energySourceId: Number(draft.energySourceId),
      billMonth: draft.billMonth,
      billedQty: draft.billedQty.trim(),
      billedAmount: draft.billedAmount.trim(),
      note: draft.note.trim() || null,
    });
    if (r?.id) {
      setDraft(EMPTY);
      setDone(
        `${r.billMonth} ${r.sourceCode} 고지서를 대조했습니다.` +
          (r.coverage?.partial
            ? ` 계측이 ${r.coverage.days}일분뿐이라 산정 금액이 한 달치가 아닙니다.`
            : ""),
      );
    }
  }

  return (
    <>
      <PageTitle
        id="F-23"
        title="고지서 대조"
        subtitle="실제 청구 금액과 산정 금액을 견주고 차이 사유를 남깁니다"
        help="fems/f-23"
      />
      <ErrorNotice error={Object.keys(errors).length ? undefined : error} />
      {done && <p role="status">{done}</p>}
      <div className="field-row">
        <label>
          에너지원
          <select
            value={draft.energySourceId}
            onChange={(e) =>
              setDraft({ ...draft, energySourceId: e.target.value })
            }
          >
            <option value="">선택</option>
            {billable.map((s) => (
              <option key={s.id} value={s.id}>
                {s.sourceCode} {s.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          청구 월
          <input
            type="month"
            value={draft.billMonth}
            onChange={(e) => setDraft({ ...draft, billMonth: e.target.value })}
          />
        </label>
        <Field
          label="청구 사용량"
          inputMode="decimal"
          value={draft.billedQty}
          required
          error={errors.billedQty}
          onChange={(e) => setDraft({ ...draft, billedQty: e.target.value })}
        />
        <Field
          label="청구 금액 (원)"
          inputMode="decimal"
          value={draft.billedAmount}
          required
          error={errors.billedAmount}
          onChange={(e) => setDraft({ ...draft, billedAmount: e.target.value })}
        />
        <Field
          label="차이 사유"
          value={draft.note}
          maxLength={300}
          error={errors.note}
          onChange={(e) => setDraft({ ...draft, note: e.target.value })}
        />
        <button
          type="button"
          disabled={
            pending ||
            !draft.energySourceId ||
            !draft.billMonth ||
            !draft.billedQty.trim() ||
            !draft.billedAmount.trim()
          }
          onClick={() => void save()}
        >
          대조
        </button>
      </div>
      <p className="muted" role="note">
        산정 금액은 <strong>입력한 그 시점의 값</strong>으로 굳습니다 — 나중에
        계측이 바뀌어도 이 고지서와 견준 값은 그대로 남습니다. 산정과 다르면{" "}
        <strong>차이 사유</strong>를 적어야 합니다. 같은 달 고지서는 하나이고,
        잘못 넣었으면 지우고 다시 넣으세요.
      </p>
      {!bills ? (
        !lists.error && <Loading delay={300} />
      ) : bills.length === 0 ? (
        <p className="muted">대조한 고지서가 없습니다.</p>
      ) : (
        <div className="table-scroll">
          <table aria-label="고지서 대조">
            <thead>
              <tr>
                <th scope="col">월</th>
                <th scope="col">에너지원</th>
                <th scope="col" className="num">
                  청구
                </th>
                <th scope="col" className="num">
                  산정
                </th>
                <th scope="col" className="num">
                  차이
                </th>
                <th scope="col">사유</th>
                <th scope="col">관리</th>
              </tr>
            </thead>
            <tbody>
              {bills.map((b) => {
                const diff = Number(b.difference);
                return (
                  <tr key={b.id}>
                    <th scope="row">{b.billMonth}</th>
                    <td>{b.sourceCode}</td>
                    <td className="num">{won(b.billedAmount)}</td>
                    <td className="num">{won(b.calculatedAmount)}</td>
                    <td className="num">
                      {diff === 0 ? (
                        "일치"
                      ) : (
                        <Badge tone="warning">
                          {diff > 0 ? "+" : ""}
                          {won(b.difference)}
                          {/* 산정이 0이면 비율은 0%가 아니라 낼 수 없는 값이다. */}
                          {b.differenceRate !== null &&
                            ` (${Number(b.differenceRate)}%)`}
                        </Badge>
                      )}
                    </td>
                    <td className="wrap">{b.note ?? "—"}</td>
                    <td>
                      <button
                        type="button"
                        className="link-button"
                        disabled={pending}
                        onClick={() =>
                          void send(`/utility-bills/${b.id}`, "DELETE")
                        }
                      >
                        지우기
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
