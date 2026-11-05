// W-06 창고·위치 — 창고 목록 → 위치 상세 → 위치 폼(UI-03 P 패턴, F-12 기준). 폼을 닫으면 위치 상세로 돌아간다.
// 용도(원자재·완제품)별 활성 창고 1개, 창고마다 기본 위치 1개가 원천 반영 입출고 위치다(FS-024 4.1·4.2).
import { useEffect, useState, type FormEvent } from "react";
import { api } from "../shared/api";
import {
  Badge,
  DataTable,
  DetailPanel,
  EmptyState,
  ErrorNotice,
  Field,
  FormPanel,
  Loading,
  PageTitle,
  useDiscardGuard,
  type Column,
} from "../shared/components";
import {
  fieldErrors,
  ModuleOff,
  moduleOff,
  PURPOSE_LABEL,
  useLists,
  useSend,
  WMS,
  type Location,
  type LocationType,
  type Purpose,
  type Warehouse,
} from "./common";

type Panel =
  | { kind: "warehouse"; row: Warehouse | null }
  | { kind: "locations"; warehouse: Warehouse }
  | { kind: "location"; warehouse: Warehouse; row: Location | null };
type Draft = {
  code: string;
  name: string;
  purpose: Purpose;
  isActive: boolean;
  isDefault: boolean;
  locationType: LocationType;
  capacityQty: string;
  mixItems: boolean;
  mixLots: boolean;
};
const EMPTY: Draft = {
  code: "",
  name: "",
  purpose: "RAW",
  isActive: true,
  isDefault: false,
  locationType: "NORMAL",
  capacityQty: "",
  mixItems: true,
  mixLots: true,
};

export function Warehouses() {
  const { data, error, reload } = useLists<[Warehouse[]]>(["/warehouses"]);
  const [panel, setPanel] = useState<Panel | null>(null);
  const [locations, setLocations] = useState<Location[]>();
  const [tick, setTick] = useState(0);
  const refresh = () => {
    reload();
    setTick((n) => n + 1);
  };
  const {
    send,
    pending,
    error: saveError,
    setError,
    deleteButtons,
  } = useSend(refresh);
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [initial, setInitial] = useState<Draft>(EMPTY);
  const editingForm = panel?.kind === "warehouse" || panel?.kind === "location";
  const guard = useDiscardGuard(
    editingForm && JSON.stringify(draft) !== JSON.stringify(initial),
  );
  const warehouseId =
    panel && panel.kind !== "warehouse" ? panel.warehouse.id : null;
  useEffect(() => {
    if (!warehouseId) return;
    setLocations(undefined);
    void api<Location[]>(`${WMS}/warehouses/${warehouseId}/locations`)
      .then((r) => setLocations(r.data))
      .catch(setError);
  }, [warehouseId, tick]);
  if (moduleOff(error)) return <ModuleOff />;
  const rows = data?.[0];
  const errors = fieldErrors(saveError);

  function openForm(next: Panel, values: Draft) {
    setPanel(next);
    setDraft(values);
    setInitial(values);
    setError(undefined);
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!panel) return;
    if (panel.kind === "warehouse") {
      const saved = panel.row
        ? await send(`/warehouses/${panel.row.id}`, "PATCH", {
            name: draft.name,
            isActive: draft.isActive,
          })
        : await send("/warehouses", "POST", {
            code: draft.code.trim().toUpperCase(),
            name: draft.name,
            purpose: draft.purpose,
            isActive: draft.isActive,
          });
      if (saved) setPanel(null);
    } else if (panel.kind === "location") {
      const saved = panel.row
        ? await send(`/locations/${panel.row.id}`, "PATCH", {
            name: draft.name,
            isActive: draft.isActive,
            locationType: draft.locationType,
            capacityQty: draft.capacityQty.trim() || null,
            mixItems: draft.mixItems,
            mixLots: draft.mixLots,
            ...(draft.isDefault && !panel.row.isDefault
              ? { isDefault: true }
              : {}),
          })
        : await send(`/warehouses/${panel.warehouse.id}/locations`, "POST", {
            code: draft.code.trim().toUpperCase(),
            name: draft.name,
            isDefault: draft.isDefault,
            locationType: draft.locationType,
            capacityQty: draft.capacityQty.trim() || null,
            mixItems: draft.mixItems,
            mixLots: draft.mixLots,
          });
      if (saved) setPanel({ kind: "locations", warehouse: panel.warehouse });
    }
  }

  const columns: Column<Warehouse>[] = [
    { key: "code", label: "코드" },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <span className="row-actions">
          <button
            type="button"
            className="link-button"
            aria-pressed={panel?.kind !== "warehouse" && warehouseId === r.id}
            onClick={() =>
              guard.guard(() => setPanel({ kind: "locations", warehouse: r }))
            }
          >
            위치 {r.locationCount}
          </button>
          <button
            type="button"
            className="link-button"
            onClick={() =>
              guard.guard(() =>
                openForm(
                  { kind: "warehouse", row: r },
                  {
                    ...EMPTY,
                    code: r.code,
                    name: r.name,
                    purpose: r.purpose,
                    isActive: r.isActive,
                  },
                ),
              )
            }
          >
            수정
          </button>
        </span>
      ),
    },
    { key: "name", label: "이름" },
    { key: "purpose", label: "용도", render: (r) => PURPOSE_LABEL[r.purpose] },
    {
      key: "isActive",
      label: "사용",
      render: (r) =>
        r.isActive ? (
          <Badge>사용</Badge>
        ) : (
          <Badge tone="warning">사용 안 함</Badge>
        ),
    },
  ];

  const parent = panel && panel.kind !== "warehouse" ? panel.warehouse : null;
  return (
    <div className="page-fill">
      <PageTitle
        id="W-06"
        title="창고·위치"
        subtitle="원자재·완제품 창고와 창고 안 보관 위치입니다. 기본 위치로 MES·ERP 기록이 반영됩니다"
        help="wms/w-06"
        actions={
          <button
            type="button"
            aria-pressed={panel?.kind === "warehouse" && !panel.row}
            onClick={() =>
              guard.guard(() =>
                openForm({ kind: "warehouse", row: null }, EMPTY),
              )
            }
          >
            창고 등록
          </button>
        }
      />
      {!panel && <ErrorNotice error={saveError} />}
      <ErrorNotice error={error} retry={reload} />
      {!rows ? (
        !error && <Loading />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <DataTable
              rows={rows}
              columns={columns}
              caption="창고 목록"
              offset={0}
              total={rows.length}
              limit={rows.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="창고가 없습니다. 원자재 창고와 완제품 창고를 먼저 등록하세요."
                  action="창고 등록"
                  onAction={() =>
                    openForm({ kind: "warehouse", row: null }, EMPTY)
                  }
                />
              }
            />
          </section>
          {panel?.kind === "locations" && parent && (
            <DetailPanel
              wide
              title={`${parent.code} 위치`}
              onClose={() => setPanel(null)}
              actions={
                <button
                  type="button"
                  onClick={() =>
                    openForm(
                      { kind: "location", warehouse: parent, row: null },
                      EMPTY,
                    )
                  }
                >
                  위치 추가
                </button>
              }
            >
              <ErrorNotice
                error={Object.keys(errors).length ? undefined : saveError}
              />
              {!locations ? (
                <Loading />
              ) : locations.length ? (
                <div className="table-scroll">
                  <table>
                    <caption>{parent.name} 위치</caption>
                    <thead>
                      <tr>
                        <th scope="col">코드</th>
                        <th scope="col">이름</th>
                        <th scope="col">유형</th>
                        <th scope="col">기본</th>
                        <th scope="col">사용</th>
                        <th scope="col">관리</th>
                      </tr>
                    </thead>
                    <tbody>
                      {locations.map((l) => (
                        <tr key={l.id}>
                          <td>{l.code}</td>
                          <td>{l.name}</td>
                          <td>
                            {l.locationType === "QUARANTINE" ? "격리" : "정상"}
                          </td>
                          <td>{l.isDefault ? <Badge>기본</Badge> : "—"}</td>
                          <td>{l.isActive ? "사용" : "사용 안 함"}</td>
                          <td>
                            <span className="row-actions">
                              <button
                                type="button"
                                className="link-button"
                                onClick={() =>
                                  openForm(
                                    {
                                      kind: "location",
                                      warehouse: parent,
                                      row: l,
                                    },
                                    {
                                      ...EMPTY,
                                      code: l.code,
                                      name: l.name,
                                      isActive: l.isActive,
                                      isDefault: l.isDefault,
                                      locationType: l.locationType ?? "NORMAL",
                                      capacityQty: l.capacityQty ?? "",
                                      mixItems: l.mixItems ?? true,
                                      mixLots: l.mixLots ?? true,
                                    },
                                  )
                                }
                              >
                                수정
                              </button>
                              {!l.isDefault &&
                                deleteButtons(
                                  `l:${l.id}`,
                                  `/locations/${l.id}`,
                                )}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="muted">
                  위치가 없습니다. 첫 위치가 기본 위치가 됩니다.
                </p>
              )}
            </DetailPanel>
          )}
          {panel && panel.kind !== "locations" && (
            <FormPanel
              key={`${panel.kind}:${panel.row?.id ?? "new"}`}
              title={
                panel.kind === "warehouse"
                  ? panel.row
                    ? `${panel.row.code} 수정`
                    : "창고 등록"
                  : panel.row
                    ? `${panel.warehouse.code} ${panel.row.code} 수정`
                    : `${panel.warehouse.code} 위치 추가`
              }
              guard={guard}
              onClose={() =>
                panel.kind === "location"
                  ? setPanel({ kind: "locations", warehouse: panel.warehouse })
                  : setPanel(null)
              }
              onSubmit={(e) => void submit(e)}
              actions={
                <>
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    {panel.row ? "저장" : "등록"}
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() =>
                      guard.guard(() =>
                        panel.kind === "location"
                          ? setPanel({
                              kind: "locations",
                              warehouse: panel.warehouse,
                            })
                          : setPanel(null),
                      )
                    }
                  >
                    취소
                  </button>
                </>
              }
            >
              <ErrorNotice
                error={Object.keys(errors).length ? undefined : saveError}
              />
              <Field
                label="코드"
                value={draft.code}
                required
                disabled={!!panel.row}
                maxLength={20}
                pattern="[A-Z][A-Z0-9\-]{1,19}"
                title="영문 대문자로 시작하는 2~20자 (대문자·숫자·-)"
                error={errors.code}
                onChange={(e) =>
                  setDraft({ ...draft, code: e.target.value.toUpperCase() })
                }
              />
              <Field
                label="이름"
                value={draft.name}
                required
                maxLength={100}
                error={errors.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
              />
              {panel.kind === "warehouse" && (
                <div className="field">
                  <label htmlFor="wms-purpose">용도</label>
                  <select
                    id="wms-purpose"
                    value={draft.purpose}
                    disabled={!!panel.row}
                    aria-invalid={!!errors.purpose}
                    onChange={(e) =>
                      setDraft({ ...draft, purpose: e.target.value as Purpose })
                    }
                  >
                    <option value="RAW">
                      원자재 — ERP 매입 입고·MES 투입 차감
                    </option>
                    <option value="FG">완제품 — MES 입고·ERP 출하 차감</option>
                  </select>
                  {errors.purpose && <small>{errors.purpose}</small>}
                </div>
              )}
              {panel.kind === "location" && (
                <label>
                  위치 유형
                  <select
                    value={draft.locationType}
                    onChange={(e) => {
                      const nextType = e.target.value as LocationType;
                      setDraft({
                        ...draft,
                        locationType: nextType,
                        isDefault:
                          nextType === "NORMAL" ? draft.isDefault : false,
                      });
                    }}
                  >
                    <option value="NORMAL">정상</option>
                    <option value="RECEIVING">입고장</option>
                    <option value="SHIPPING">출고장</option>
                    <option value="LINE">라인</option>
                    <option value="QUARANTINE">격리</option>
                    <option value="RETURN">반품</option>
                  </select>
                </label>
              )}
              {panel.kind === "location" && (
                <>
                  <label>
                    용량 (비우면 제한 없음)
                    <input
                      value={draft.capacityQty}
                      inputMode="decimal"
                      onChange={(e) =>
                        setDraft({ ...draft, capacityQty: e.target.value })
                      }
                    />
                    {errors.capacityQty && <small>{errors.capacityQty}</small>}
                  </label>
                  <label className="inline-check">
                    <input
                      type="checkbox"
                      checked={draft.mixItems}
                      onChange={(e) =>
                        setDraft({ ...draft, mixItems: e.target.checked })
                      }
                    />
                    다른 품목 혼적 허용
                  </label>
                  <label className="inline-check">
                    <input
                      type="checkbox"
                      checked={draft.mixLots}
                      onChange={(e) =>
                        setDraft({ ...draft, mixLots: e.target.checked })
                      }
                    />
                    다른 LOT 혼적 허용
                  </label>
                </>
              )}
              {panel.kind === "location" && (
                <label className="inline-check">
                  <input
                    type="checkbox"
                    checked={draft.isDefault}
                    disabled={
                      !!panel.row?.isDefault || draft.locationType !== "NORMAL"
                    }
                    onChange={(e) =>
                      setDraft({ ...draft, isDefault: e.target.checked })
                    }
                  />
                  기본 위치(원천 반영 입출고 위치)
                </label>
              )}
              {!(panel.kind === "location" && !panel.row) && (
                <label className="inline-check">
                  <input
                    type="checkbox"
                    checked={draft.isActive}
                    disabled={panel.kind === "location" && draft.isDefault}
                    onChange={(e) =>
                      setDraft({ ...draft, isActive: e.target.checked })
                    }
                  />
                  사용
                </label>
              )}
              {(errors.isActive || errors.isDefault) && (
                <small className="field-error">
                  {errors.isActive ?? errors.isDefault}
                </small>
              )}
            </FormPanel>
          )}
        </div>
      )}
    </div>
  );
}
