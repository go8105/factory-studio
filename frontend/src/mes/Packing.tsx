// M-08 패킹 — LOT 양품을 BOX에 담고, 닫힌 BOX를 PALLET에 묶는다(수량 입력 방식) (FS-020f)
import { useState, type FormEvent } from "react";
import {
  Badge,
  DataTable,
  ErrorNotice,
  Field,
  FormPanel,
  Loading,
  PageTitle,
  useDiscardGuard,
  type Column,
} from "../shared/components";
import { fieldErrors, ModuleOff, moduleOff, useLists, useSend } from "./common";

type Member = {
  id: number;
  lotId: number;
  lotNo: string;
  itemId: number;
  unit: string;
  packedQty: string;
};
export type PackingUnit = {
  id: number;
  packingNo: string;
  packingKind: "BOX" | "PALLET";
  parentPackingUnitId: number | null;
  parentPackingNo: string | null;
  status: "open" | "closed" | "received" | "shipped";
  displayStatus: "open" | "closed" | "received" | "shipped";
  receivedAt: string | null;
  members: Member[];
  childIds: number[];
  itemId: number | null;
  unit: string | null;
  totalQty: string;
};
type PackableLot = {
  lotId: number;
  lotNo: string;
  itemId: number;
  unit: string;
  finalGoodQty: string;
  packedQty: string;
  remainingQty: string;
  // QMS 보류(FS-023 D10): 표시만 하고 패킹을 막지 않는다. QMS를 끄면 null.
  qualityHold?: boolean | null;
};
type Item = { id: number; itemCode: string; name: string };

const num = (v: string) => Number(v).toLocaleString();
const STATUS: Record<
  PackingUnit["status"],
  [string, "normal" | "warning" | "issue"]
> = {
  open: ["열림", "warning"],
  closed: ["닫힘", "normal"],
  received: ["입고", "normal"],
  shipped: ["출하", "normal"],
};

export function UnitStatus({ unit }: { unit: PackingUnit }) {
  const [label, tone] = STATUS[unit.displayStatus];
  return <Badge tone={tone}>{label}</Badge>;
}

export function Packing() {
  const { data, error, reload } = useLists<
    [PackingUnit[], PackableLot[], Item[]]
  >(["/packing-units", "/packable-lots", "/items"]);
  const {
    send,
    pending,
    error: saveError,
    setError,
    deleteButtons,
  } = useSend(reload);
  const [selectedId, setSelectedId] = useState<number>();
  const [member, setMember] = useState({ lotId: 0, qty: "" });
  const [pallet, setPallet] = useState<number>();
  const [kindFilter, setKindFilter] = useState("");

  const dirty = Boolean(selectedId && member.qty.trim());
  const guard = useDiscardGuard(dirty);

  if (moduleOff(error)) return <ModuleOff />;
  const [units, lots, items] = data ?? [undefined, [], []];
  const errors = fieldErrors(saveError);
  const itemCode = (id: number | null) =>
    id === null
      ? "-"
      : (items.find((i) => i.id === id)?.itemCode ?? String(id));
  const selected = units?.find((u) => u.id === selectedId);
  const byId = (id: number) => units?.find((u) => u.id === id);

  const choices = lots.filter(
    (l) => selected?.itemId == null || l.itemId === selected.itemId,
  );
  const openPallets = (units ?? []).filter(
    (u) =>
      u.packingKind === "PALLET" &&
      u.status === "open" &&
      (u.itemId === null ||
        (u.itemId === selected?.itemId && u.unit === selected?.unit)),
  );
  const shown = (units ?? []).filter(
    (u) => !kindFilter || u.packingKind === kindFilter,
  );

  function select(id: number) {
    setSelectedId(id);
    setError(undefined);
    setMember({ lotId: 0, qty: "" });
    setPallet(undefined);
  }

  function closePanel() {
    setSelectedId(undefined);
    setMember({ lotId: 0, qty: "" });
    setPallet(undefined);
    setError(undefined);
  }

  async function create(kind: "BOX" | "PALLET") {
    const made = await send<PackingUnit>("/packing-units", "POST", {
      packingKind: kind,
    });
    if (made) select(made.id);
  }

  async function submitMember(event: FormEvent) {
    event.preventDefault();
    if (pending || !selected) return;
    const lot = choices.find(
      (l) => l.lotId === (member.lotId || choices[0]?.lotId),
    );
    if (!lot) return;
    const ok = await send(`/packing-units/${selected.id}/members`, "PUT", {
      lotId: lot.lotId,
      packedQty: (member.qty || String(Number(lot.remainingQty))).trim(),
    });
    if (ok) setMember({ lotId: 0, qty: "" });
  }

  const lotColumns: Column<PackableLot & { id: number }>[] = [
    {
      key: "lotNo",
      label: "LOT",
      render: (r) => (
        <>
          {r.lotNo} {r.qualityHold && <Badge tone="issue">QMS 보류</Badge>}
        </>
      ),
    },
    { key: "itemId", label: "품목", render: (r) => itemCode(r.itemId) },
    {
      key: "finalGoodQty",
      label: "최종 양품",
      render: (r) => num(r.finalGoodQty),
    },
    { key: "packedQty", label: "담음", render: (r) => num(r.packedQty) },
    { key: "remainingQty", label: "잔여", render: (r) => num(r.remainingQty) },
  ];

  const unitColumns: Column<PackingUnit>[] = [
    { key: "packingNo", label: "포장 번호" },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <span className="row-actions">
          <button
            type="button"
            className="link-button"
            aria-pressed={r.id === selectedId}
            onClick={() => guard.guard(() => select(r.id))}
          >
            열기
          </button>
          {r.status === "open" &&
            r.members.length === 0 &&
            r.childIds.length === 0 &&
            deleteButtons(`unit:${r.id}`, `/packing-units/${r.id}`)}
        </span>
      ),
    },
    { key: "packingKind", label: "종류" },
    { key: "status", label: "상태", render: (r) => <UnitStatus unit={r} /> },
    { key: "itemId", label: "품목", render: (r) => itemCode(r.itemId) },
    { key: "totalQty", label: "수량", render: (r) => num(r.totalQty) },
    {
      key: "parentPackingNo",
      label: "PALLET",
      render: (r) =>
        r.packingKind === "BOX"
          ? (r.parentPackingNo ?? "-")
          : `BOX ${r.childIds.length}`,
    },
  ];

  const memberColumns: Column<Member>[] = [
    { key: "lotNo", label: "LOT" },
    {
      key: "id",
      label: "관리",
      render: (r) =>
        selected?.status === "open" ? (
          <button
            type="button"
            className="link-button"
            onClick={() =>
              void send(`/packing-units/${selected.id}/members`, "PUT", {
                lotId: r.lotId,
                packedQty: "0",
              })
            }
          >
            빼기
          </button>
        ) : (
          "-"
        ),
    },
    {
      key: "packedQty",
      label: "수량",
      render: (r) => `${num(r.packedQty)} ${r.unit}`,
    },
  ];

  return (
    <div className="page-fill">
      <PageTitle
        id="M-08"
        title="패킹"
        subtitle="LOT 양품을 BOX에 담고, 닫힌 BOX를 PALLET에 묶습니다"
        help="mes/m-08"
      />
      <p className="muted" role="note">
        BOX → PALLET 2단 포장이며 한 포장에는 한 품목만 담습니다. LOT마다 최종
        양품을 넘겨 담을 수 없고, 전량 불량 LOT은 담을 수 없습니다. 닫은 BOX의
        내용과 닫은 PALLET의 구성은 바꿀 수 없습니다.
      </p>
      {!selected && (
        <ErrorNotice
          error={Object.keys(errors).length ? undefined : saveError}
        />
      )}
      <ErrorNotice error={error} retry={reload} />
      {!units ? (
        !error && <Loading />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <div className="section-block">
              <h2>담을 수 있는 LOT</h2>
              {lots.some((l) => l.qualityHold) && (
                <p className="muted" role="note">
                  QMS 보류는 표시만 하며 패킹을 막지 않습니다. 처분은 QMS 품질
                  보류에서 합니다.
                </p>
              )}
              <DataTable
                rows={lots.map((l) => ({ ...l, id: l.lotId }))}
                columns={lotColumns}
                caption="담을 수 있는 LOT"
                offset={0}
                total={lots.length}
                limit={lots.length || 1}
                onPage={() => undefined}
                empty={
                  <p className="muted">담을 양품이 남은 LOT이 없습니다.</p>
                }
              />
            </div>
            <div className="section-block">
              <div className="filter-bar">
                <button
                  type="button"
                  className="secondary"
                  disabled={pending}
                  onClick={() => void create("BOX")}
                >
                  새 BOX
                </button>
                <button
                  type="button"
                  className="secondary"
                  disabled={pending}
                  onClick={() => void create("PALLET")}
                >
                  새 PALLET
                </button>
                <label htmlFor="unit-kind">종류:</label>
                <select
                  id="unit-kind"
                  value={kindFilter}
                  onChange={(e) => setKindFilter(e.target.value)}
                >
                  <option value="">전체</option>
                  <option value="BOX">BOX</option>
                  <option value="PALLET">PALLET</option>
                </select>
              </div>
              <DataTable
                rows={shown}
                columns={unitColumns}
                caption="포장 목록"
                offset={0}
                total={shown.length}
                limit={shown.length || 1}
                onPage={() => undefined}
                empty={
                  <p className="muted">포장이 없습니다. 새 BOX를 만드세요.</p>
                }
              />
            </div>
          </section>
          {selected && (
            <FormPanel
              key={selected.id}
              title={selected.packingNo}
              guard={guard}
              onClose={closePanel}
              onSubmit={(e) => {
                e.preventDefault();
                if (
                  selected.packingKind === "BOX" &&
                  selected.status === "open"
                ) {
                  void submitMember(e);
                }
              }}
              actions={
                <button
                  type="button"
                  className="secondary"
                  onClick={() => guard.guard(closePanel)}
                >
                  닫기
                </button>
              }
            >
              <div className="field">
                <span className="label">포장 번호</span>
                <p>
                  <strong>{selected.packingNo}</strong>{" "}
                  <UnitStatus unit={selected} />
                </p>
              </div>
              <ErrorNotice
                error={Object.keys(errors).length ? undefined : saveError}
              />
              {selected.packingKind === "BOX" ? (
                <>
                  <DataTable
                    rows={selected.members}
                    columns={memberColumns}
                    caption={`${selected.packingNo} 구성`}
                    offset={0}
                    total={selected.members.length}
                    limit={selected.members.length || 1}
                    onPage={() => undefined}
                    empty={<p className="muted">비어 있습니다.</p>}
                  />
                  {selected.status === "open" && (
                    <section aria-label="LOT 담기">
                      {choices.length === 0 ? (
                        <p className="muted">
                          이 BOX에 담을 수 있는 LOT이 없습니다.
                        </p>
                      ) : (
                        <>
                          <div className="field">
                            <label htmlFor="member-lot">LOT</label>
                            <select
                              id="member-lot"
                              value={member.lotId || choices[0].lotId}
                              onChange={(e) =>
                                setMember({
                                  lotId: Number(e.target.value),
                                  qty: "",
                                })
                              }
                            >
                              {choices.map((l) => (
                                <option key={l.lotId} value={l.lotId}>
                                  {l.lotNo} · {itemCode(l.itemId)} · 잔여{" "}
                                  {num(l.remainingQty)}
                                </option>
                              ))}
                            </select>
                            {errors.lotId && <small>{errors.lotId}</small>}
                          </div>
                          <Field
                            label="담을 수량"
                            value={member.qty}
                            placeholder="비우면 잔여 전량"
                            inputMode="decimal"
                            error={errors.packedQty}
                            onChange={(e) =>
                              setMember({ ...member, qty: e.target.value })
                            }
                          />
                        </>
                      )}
                      <div className="form-actions">
                        <button
                          type="submit"
                          disabled={pending || choices.length === 0}
                        >
                          담기
                        </button>
                        <button
                          type="button"
                          className="secondary"
                          disabled={pending || selected.members.length === 0}
                          onClick={() =>
                            void send(
                              `/packing-units/${selected.id}/close`,
                              "POST",
                            )
                          }
                        >
                          BOX 닫기
                        </button>
                      </div>
                    </section>
                  )}
                  {selected.status === "closed" &&
                    selected.displayStatus === "closed" && (
                      <div className="form-actions">
                        {selected.parentPackingUnitId === null ? (
                          <>
                            <label
                              htmlFor="box-pallet"
                              className="filter-inline"
                            >
                              묶을 PALLET
                            </label>
                            <select
                              id="box-pallet"
                              value={pallet ?? openPallets[0]?.id ?? ""}
                              onChange={(e) =>
                                setPallet(Number(e.target.value))
                              }
                            >
                              {openPallets.map((p) => (
                                <option key={p.id} value={p.id}>
                                  {p.packingNo}
                                </option>
                              ))}
                            </select>
                            <button
                              type="button"
                              disabled={pending || openPallets.length === 0}
                              onClick={() =>
                                void send(
                                  `/packing-units/${selected.id}/parent`,
                                  "PUT",
                                  {
                                    parentPackingUnitId:
                                      pallet ?? openPallets[0]?.id,
                                  },
                                )
                              }
                            >
                              PALLET에 묶기
                            </button>
                          </>
                        ) : (
                          byId(selected.parentPackingUnitId)?.status ===
                            "open" && (
                            <button
                              type="button"
                              className="secondary"
                              disabled={pending}
                              onClick={() =>
                                void send(
                                  `/packing-units/${selected.id}/parent`,
                                  "PUT",
                                  {
                                    parentPackingUnitId: null,
                                  },
                                )
                              }
                            >
                              {selected.parentPackingNo}에서 풀기
                            </button>
                          )
                        )}
                      </div>
                    )}
                </>
              ) : (
                <>
                  <p className="muted">
                    {itemCode(selected.itemId)} · 총 {num(selected.totalQty)}{" "}
                    {selected.unit ?? ""} · BOX {selected.childIds.length}개
                  </p>
                  <p className="muted">
                    {selected.childIds
                      .map((id) => byId(id)?.packingNo)
                      .join(", ") ||
                      "묶인 BOX가 없습니다. 닫힌 BOX를 열어 이 PALLET에 묶으세요."}
                  </p>
                  {selected.status === "open" && (
                    <div className="form-actions">
                      <button
                        type="button"
                        disabled={pending || selected.childIds.length === 0}
                        onClick={() =>
                          void send(
                            `/packing-units/${selected.id}/close`,
                            "POST",
                          )
                        }
                      >
                        PALLET 닫기
                      </button>
                    </div>
                  )}
                  {selected.status === "closed" && (
                    <p className="muted">
                      닫힌 PALLET은 완제품 입고 화면에서 입고합니다.
                    </p>
                  )}
                </>
              )}
            </FormPanel>
          )}
        </div>
      )}
    </div>
  );
}
