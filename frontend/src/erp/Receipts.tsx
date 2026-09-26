// E-10 수금 등록·소명 · E-13 지급 등록·소명 — 확정, 원천별 소명(FIFO 제안), 소명 취소
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
import {
  RECEIVABLE,
  toMoney,
  toOpen,
  type Application,
  type Money,
  type OpenItem,
  type Side,
} from "./settlement";

type Raw = Record<string, unknown>;
const today = () => new Date().toLocaleDateString("sv-SE");

/** 한도 초과(409 LIMIT_EXCEEDED)는 어느 쪽이 넘었는지 풀어 쓴다. */
function limitText(side: Side, error: unknown) {
  if (!(error instanceof ApiError) || error.error.code !== "LIMIT_EXCEEDED")
    return undefined;
  const d = error.error.details as Record<string, string>;
  return d.limit === "RECEIVABLE" || d.limit === "PAYABLE"
    ? `${d[side.docKey]} ${side.item}의 남은 잔액은 ${won(d.availableAmount)}입니다. 전체 소명을 저장하지 않았습니다.`
    : `이 ${side.money}의 미소명 잔여는 ${won(d.availableAmount)}입니다. 전체 소명을 저장하지 않았습니다.`;
}

export function Receipts({ side = RECEIVABLE }: { side?: Side }) {
  const receivable = side === RECEIVABLE;
  const { fail } = useSession();
  const { data, error, reload } = useLists<[Raw[], Raw[], Partner[]]>([
    side.moneyPath,
    side.openPath,
    PARTNERS,
  ]);
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
  const blank = { no: "", partnerId: 0, on: today(), amount: "" };
  const [create, setCreate] = useState(blank);

  if (moduleOff(error)) return <ModuleOff />;
  const monies = data?.[0].map(toMoney(side));
  const items: OpenItem[] = data?.[1].map(toOpen(side)) ?? [];
  const partners = (data?.[2] ?? []).filter(
    (p) => p.partnerKind === side.partnerKind && p.isActive,
  );
  const name = labels(data?.[2] ?? [], []);
  const errors = fieldErrors(saveError);
  const limit = limitText(side, saveError);
  const selected = monies?.find((r) => r.id === selectedId);
  const open = items.filter(
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
    const created = await send<Raw>(side.moneyPath, "POST", {
      [side.noKey]: create.no.trim().toUpperCase(),
      partnerId: create.partnerId || partners[0]?.id,
      [side.onKey]: create.on,
      amount: create.amount.trim(),
    });
    if (created) {
      setCreate(blank);
      select(created.id as number);
    }
  }

  async function fifo() {
    if (!selected) return;
    try {
      const r = await api<Raw[]>(
        `${ERP}${side.moneyPath}/${selected.id}/fifo-suggestion`,
      );
      // 제안만 채운다. 저장은 사용자가 고친 뒤 "소명 저장"으로 한다.
      setAmounts(
        Object.fromEntries(
          r.data.map((s) => [s[side.itemKey], String(Number(s.amount))]),
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
      .map(([id, v]) => ({ [side.itemKey]: Number(id), amount: v.trim() }));
    const saved = await send(
      `${side.moneyPath}/${selected.id}/applications`,
      "POST",
      { lines },
    );
    if (saved) setAmounts({});
  }

  async function undo(applyId: number) {
    if (!selected || pending) return;
    await send(
      `${side.moneyPath}/${selected.id}/applications/${applyId}`,
      "DELETE",
    );
    setConfirmUndo(undefined);
  }

  const columns: Column<Money>[] = [
    { key: "no", label: `${side.money}번호` },
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
                onClick={() =>
                  void send(`${side.moneyPath}/${r.id}/confirm`, "POST")
                }
              >
                확정
              </button>
              {deleteButtons(`money:${r.id}`, `${side.moneyPath}/${r.id}`)}
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
    { key: "on", label: `${side.money}일` },
    { key: "amount", label: `${side.money}액`, render: (r) => won(r.amount) },
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
  const targetColumns: Column<OpenItem>[] = [
    { key: "doc", label: side.doc },
    {
      key: "date",
      label: `${side.source}일`,
      render: (r) => new Date(r.date).toLocaleDateString(),
    },
    { key: "amount", label: "원금", render: (r) => won(r.amount) },
    { key: "balance", label: "잔액", render: (r) => won(r.balance) },
    {
      key: "id",
      label: "소명액",
      render: (r) => (
        <input
          aria-label={`${r.doc} 소명액`}
          inputMode="decimal"
          value={amounts[r.id] ?? ""}
          onChange={(e) => setAmounts({ ...amounts, [r.id]: e.target.value })}
        />
      ),
    },
  ];
  const appliedColumns: Column<Application>[] = [
    { key: "doc", label: side.doc },
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
        id={receivable ? "E-10" : "E-13"}
        title={`${side.money} 등록·소명`}
        subtitle={`${side.money}을 확정하고 어느 ${side.source}${side.item}에 얼마를 붙일지 소명합니다`}
        help={receivable ? "erp/e-10" : "erp/e-13"}
      />
      <p className="muted">
        확정되는 것은 {side.money}액이지 배분이 아닙니다. 확정 뒤에도 소명을
        추가하거나 취소할 수 있고, 남는 금액은 미소명 잔여로 둡니다(
        {receivable ? "과입금" : "과지급"} 허용). 소명 합계는 {side.money}액과{" "}
        {side.item} 원금을 넘을 수 없으며 서버가 최종 검증합니다.
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
      {!monies ? (
        !error && <Loading />
      ) : (
        <>
          <div className="master-grid">
            <section>
              <DataTable
                rows={monies}
                columns={columns}
                caption={`${side.money} 목록`}
                offset={0}
                total={monies.length}
                limit={monies.length || 1}
                onPage={() => undefined}
                empty={
                  <EmptyState
                    reason={`등록된 ${side.money}이 없습니다. 우측 폼에서 등록하세요.`}
                    to="#money-form"
                    action={`${side.money} 등록`}
                  />
                }
              />
            </section>
            <form
              id="money-form"
              className="panel"
              aria-label={`${side.money} 등록`}
              onSubmit={(e) => void submitCreate(e)}
            >
              <h2>새 {side.money}</h2>
              <Field
                label={`${side.money}번호`}
                value={create.no}
                required
                maxLength={40}
                placeholder={receivable ? "예: RC-0101" : "예: PM-0101"}
                error={errors[side.noKey]}
                onChange={(e) =>
                  setCreate({ ...create, no: e.target.value.toUpperCase() })
                }
              />
              <div className="field">
                <label htmlFor="money-partner">거래처</label>
                <select
                  id="money-partner"
                  value={create.partnerId || partners[0]?.id || ""}
                  onChange={(e) =>
                    setCreate({ ...create, partnerId: Number(e.target.value) })
                  }
                >
                  {partners.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.partnerCode} {p.partnerName}
                    </option>
                  ))}
                </select>
              </div>
              <Field
                label={`${side.money}일`}
                type="date"
                value={create.on}
                required
                error={errors[side.onKey]}
                onChange={(e) => setCreate({ ...create, on: e.target.value })}
              />
              <Field
                label={`${side.money}액`}
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
              <h2>{selected.no} 소명</h2>
              <p>
                {side.money}액 {won(selected.amount)} = 소명{" "}
                {won(selected.appliedAmount)} + 미소명{" "}
                {won(selected.unappliedAmount)}
              </p>
              {selected.status === "draft" ? (
                <p className="muted">
                  작성 중인 {side.money}은 먼저 확정해야 소명할 수 있습니다.
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
                    caption={`소명 대상 ${side.item}`}
                    offset={0}
                    total={open.length}
                    limit={open.length || 1}
                    onPage={() => undefined}
                    empty={
                      <p className="muted">
                        이 거래처에 잔액이 남은 {side.item}이 없습니다.
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
                caption={`${selected.no} 소명 이력`}
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
