// E-10 수금 등록·소명 — 수금 확정, 채권별 소명(FIFO 제안), 소명 취소 (FS-019e)
import { useState, type FormEvent } from "react";
import { useSession } from "../app/session";
import { api, ApiError } from "../shared/api";
import {
  Badge,
  DataTable,
  EmptyState,
  ErrorNotice,
  Field,
  Loading,
  PageTitle,
  type Column,
} from "../shared/components";
import {
  customers,
  ERP,
  fieldErrors,
  labels,
  ModuleOff,
  moduleOff,
  PARTNERS,
  useLists,
  useSend,
  won,
  type Partner,
} from "./common";
import type { Application, Receivable } from "./Receivables";

type Receipt = {
  id: number;
  receiptNo: string;
  partnerId: number;
  receivedOn: string;
  amount: string;
  status: "draft" | "confirmed";
  appliedAmount: string;
  unappliedAmount: string;
  applications: Application[];
};
const today = () => new Date().toLocaleDateString("sv-SE");

/** 한도 초과(409 LIMIT_EXCEEDED)는 어느 쪽이 넘었는지 풀어 쓴다. */
function limitText(error: unknown) {
  if (!(error instanceof ApiError) || error.error.code !== "LIMIT_EXCEEDED")
    return undefined;
  const d = error.error.details as Record<string, string>;
  return d.limit === "RECEIVABLE"
    ? `${d.shipmentNo} 채권의 남은 잔액은 ${won(d.availableAmount)}입니다. 전체 소명을 저장하지 않았습니다.`
    : `이 수금의 미소명 잔여는 ${won(d.availableAmount)}입니다. 전체 소명을 저장하지 않았습니다.`;
}

export function Receipts() {
  const { fail } = useSession();
  const { data, error, reload } = useLists<
    [Receipt[], Receivable[], Partner[]]
  >(["/receipts", "/receivables", PARTNERS]);
  const {
    send,
    pending,
    error: saveError,
    setError,
    deleteButtons,
  } = useSend(reload);
  const [selectedId, setSelectedId] = useState<number>();
  const [amounts, setAmounts] = useState<Record<number, string>>({});
  const [confirmUndo, setConfirmUndo] = useState<number>();
  const blank = {
    receiptNo: "",
    partnerId: 0,
    receivedOn: today(),
    amount: "",
  };
  const [create, setCreate] = useState(blank);

  if (moduleOff(error)) return <ModuleOff />;
  const [receipts, receivables, partners] = data ?? [undefined, [], []];
  const buyers = customers(partners);
  const name = labels(partners, []);
  const errors = fieldErrors(saveError);
  const limit = limitText(saveError);
  const selected = receipts?.find((r) => r.id === selectedId);
  const open = receivables.filter(
    (r) => r.partnerId === selected?.partnerId && Number(r.balance) > 0,
  );
  const planned = Object.values(amounts).reduce(
    (t, v) => t + (Number(v) || 0),
    0,
  );

  function select(id: number | undefined) {
    setSelectedId(id);
    setAmounts({});
    setConfirmUndo(undefined);
    setError(undefined);
  }

  async function submitCreate(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    const created = await send<Receipt>("/receipts", "POST", {
      receiptNo: create.receiptNo.trim().toUpperCase(),
      partnerId: create.partnerId || buyers[0]?.id,
      receivedOn: create.receivedOn,
      amount: create.amount.trim(),
    });
    if (created) {
      setCreate(blank);
      select(created.id);
    }
  }

  async function fifo() {
    if (!selected) return;
    try {
      const r = await api<{ receivableId: number; amount: string }[]>(
        `${ERP}/receipts/${selected.id}/fifo-suggestion`,
      );
      // 제안만 채운다. 저장은 사용자가 고친 뒤 "소명 저장"으로 한다.
      setAmounts(
        Object.fromEntries(
          r.data.map((s) => [s.receivableId, String(Number(s.amount))]),
        ),
      );
    } catch (e) {
      setError(e);
      if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
    }
  }

  async function saveApplications() {
    if (!selected || pending) return;
    const lines = Object.entries(amounts)
      .filter(([, v]) => v.trim() && Number(v) > 0)
      .map(([id, v]) => ({ receivableId: Number(id), amount: v.trim() }));
    const saved = await send(`/receipts/${selected.id}/applications`, "POST", {
      lines,
    });
    if (saved) setAmounts({});
  }

  async function undo(applyId: number) {
    if (!selected || pending) return;
    await send(`/receipts/${selected.id}/applications/${applyId}`, "DELETE");
    setConfirmUndo(undefined);
  }

  const columns: Column<Receipt>[] = [
    { key: "receiptNo", label: "수금번호" },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <span className="row-actions">
          <button
            type="button"
            className="link-button"
            aria-pressed={r.id === selectedId}
            onClick={() => select(r.id)}
          >
            소명 {r.applications.length}
          </button>
          {r.status === "draft" && (
            <>
              <button
                type="button"
                className="link-button"
                onClick={() => void send(`/receipts/${r.id}/confirm`, "POST")}
              >
                확정
              </button>
              {deleteButtons(`receipt:${r.id}`, `/receipts/${r.id}`)}
            </>
          )}
        </span>
      ),
    },
    {
      key: "partnerId",
      label: "거래처",
      render: (r) => name.partner(r.partnerId),
    },
    { key: "receivedOn", label: "수금일" },
    { key: "amount", label: "수금액", render: (r) => won(r.amount) },
    {
      key: "appliedAmount",
      label: "소명",
      render: (r) => won(r.appliedAmount),
    },
    {
      key: "unappliedAmount",
      label: "미소명",
      render: (r) => won(r.unappliedAmount),
    },
    {
      key: "status",
      label: "상태",
      render: (r) =>
        r.status === "confirmed" ? (
          <Badge>확정</Badge>
        ) : (
          <Badge tone="warning">작성</Badge>
        ),
    },
  ];
  const targetColumns: Column<Receivable>[] = [
    { key: "shipmentNo", label: "매출(출하번호)" },
    {
      key: "recognizedAt",
      label: "매출일",
      render: (r) => new Date(r.recognizedAt).toLocaleDateString(),
    },
    { key: "amount", label: "원금", render: (r) => won(r.amount) },
    { key: "balance", label: "잔액", render: (r) => won(r.balance) },
    {
      key: "id",
      label: "소명액",
      render: (r) => (
        <input
          aria-label={`${r.shipmentNo} 소명액`}
          inputMode="decimal"
          value={amounts[r.id] ?? ""}
          onChange={(e) => setAmounts({ ...amounts, [r.id]: e.target.value })}
        />
      ),
    },
  ];
  const appliedColumns: Column<Application>[] = [
    { key: "shipmentNo", label: "매출(출하번호)" },
    {
      key: "id",
      label: "관리",
      render: (a) =>
        confirmUndo === a.id ? (
          <span className="row-actions">
            <button
              type="button"
              className="secondary"
              disabled={pending}
              onClick={() => void undo(a.id)}
            >
              소명 취소 확정
            </button>
            <button
              type="button"
              className="link-button"
              onClick={() => setConfirmUndo(undefined)}
            >
              닫기
            </button>
          </span>
        ) : (
          <button
            type="button"
            className="link-button"
            onClick={() => setConfirmUndo(a.id)}
          >
            소명 취소
          </button>
        ),
    },
    { key: "amount", label: "소명액", render: (a) => won(a.amount) },
    {
      key: "appliedAt",
      label: "소명 시각",
      render: (a) => new Date(a.appliedAt).toLocaleString(),
    },
  ];

  return (
    <>
      <PageTitle
        id="E-10"
        title="수금 등록·소명"
        subtitle="수금을 확정하고 어느 매출채권에 얼마를 붙일지 소명합니다"
        help="erp/e-10"
      />
      <p className="muted">
        확정되는 것은 수금액이지 배분이 아닙니다. 확정 뒤에도 소명을 추가하거나
        취소할 수 있고, 남는 금액은 미소명 잔여로 둡니다(과입금 허용). 소명
        합계는 수금액과 채권 원금을 넘을 수 없으며 서버가 최종 검증합니다.
      </p>
      {limit ? (
        <p className="notice" role="alert">
          {limit}
        </p>
      ) : (
        <ErrorNotice
          error={Object.keys(errors).length ? undefined : saveError}
        />
      )}
      <ErrorNotice error={error} retry={reload} />
      {!receipts ? (
        !error && <Loading />
      ) : (
        <>
          <div className="master-grid">
            <section>
              <DataTable
                rows={receipts}
                columns={columns}
                caption="수금 목록"
                offset={0}
                total={receipts.length}
                limit={receipts.length || 1}
                onPage={() => undefined}
                empty={
                  <EmptyState
                    reason="등록된 수금이 없습니다. 우측 폼에서 수금을 등록하세요."
                    to="#receipt-form"
                    action="수금 등록"
                  />
                }
              />
            </section>
            <form
              id="receipt-form"
              className="panel"
              aria-label="수금 등록"
              onSubmit={(e) => void submitCreate(e)}
            >
              <h2>새 수금</h2>
              <Field
                label="수금번호"
                value={create.receiptNo}
                required
                maxLength={40}
                placeholder="예: RC-0101"
                error={errors.receiptNo}
                onChange={(e) =>
                  setCreate({
                    ...create,
                    receiptNo: e.target.value.toUpperCase(),
                  })
                }
              />
              <div className="field">
                <label htmlFor="receipt-partner">거래처</label>
                <select
                  id="receipt-partner"
                  value={create.partnerId || buyers[0]?.id || ""}
                  onChange={(e) =>
                    setCreate({ ...create, partnerId: Number(e.target.value) })
                  }
                >
                  {buyers.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.partnerCode} {p.partnerName}
                    </option>
                  ))}
                </select>
              </div>
              <Field
                label="수금일"
                type="date"
                value={create.receivedOn}
                required
                error={errors.receivedOn}
                onChange={(e) =>
                  setCreate({ ...create, receivedOn: e.target.value })
                }
              />
              <Field
                label="수금액"
                inputMode="decimal"
                value={create.amount}
                required
                error={errors.amount}
                onChange={(e) =>
                  setCreate({ ...create, amount: e.target.value })
                }
              />
              <div className="form-actions">
                <button type="submit" disabled={pending}>
                  등록
                </button>
              </div>
            </form>
          </div>

          {selected && (
            <section className="panel" aria-label="소명">
              <h2>{selected.receiptNo} 소명</h2>
              <p>
                수금액 {won(selected.amount)} = 소명{" "}
                {won(selected.appliedAmount)} + 미소명{" "}
                {won(selected.unappliedAmount)}
              </p>
              {selected.status === "draft" ? (
                <p className="muted">
                  작성 중인 수금은 먼저 확정해야 소명할 수 있습니다.
                </p>
              ) : (
                <>
                  <div className="form-actions">
                    <button
                      type="button"
                      className="secondary"
                      disabled={!open.length}
                      onClick={() => void fifo()}
                    >
                      FIFO로 채우기
                    </button>
                  </div>
                  <DataTable
                    rows={open}
                    columns={targetColumns}
                    caption="소명 대상 채권"
                    offset={0}
                    total={open.length}
                    limit={open.length || 1}
                    onPage={() => undefined}
                    empty={
                      <p className="muted">
                        이 거래처에 잔액이 남은 채권이 없습니다.
                      </p>
                    }
                  />
                  <p className="muted">
                    이번 소명 {won(String(planned))} · 저장 후 미소명{" "}
                    {won(String(Number(selected.unappliedAmount) - planned))}
                  </p>
                  {errors.lines && <p className="notice">{errors.lines}</p>}
                  <div className="form-actions">
                    <button
                      type="button"
                      disabled={pending || planned <= 0}
                      onClick={() => void saveApplications()}
                    >
                      소명 저장
                    </button>
                  </div>
                </>
              )}
              <h3>소명 이력</h3>
              <p className="muted">
                소명 취소는 기록을 지우고, 이 기록은 운영 기록(감사)에 남습니다.
              </p>
              <DataTable
                rows={selected.applications}
                columns={appliedColumns}
                caption={`${selected.receiptNo} 소명 이력`}
                offset={0}
                total={selected.applications.length}
                limit={selected.applications.length || 1}
                onPage={() => undefined}
                empty={<p className="muted">소명이 없습니다.</p>}
              />
            </section>
          )}
        </>
      )}
    </>
  );
}
