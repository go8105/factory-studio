// Q-04 검사 — 목록 + 넓은 측정값 입력 패널(UI-03 W 패턴, E-04 기준).
// 판정은 입력 즉시 미리 보이고, 저장·확정 응답의 서버 판정으로 덮는다. 확정은 불변이며 정정은 재검사다.
import { useEffect, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useSession } from "../app/session";
import { api, ApiError } from "../shared/api";
import {
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
  limitText,
  ModuleOff,
  moduleOff,
  num,
  previewJudgement,
  QMS,
  ResultBadge,
  SOURCE,
  useSend,
  type DefectType,
  type Inspection,
  type InspectionValue,
  SpcBadge,
} from "./common";

type Entry = { measured: string; passed: boolean | null; defect: string };
type Draft = { sample: string; note: string; entries: Record<number, Entry> };
type Manual = {
  lotNo: string;
  itemCode: string;
  itemName: string;
  lotQty: string;
  unit: string;
  sample: string;
};
const EMPTY_MANUAL: Manual = {
  lotNo: "",
  itemCode: "",
  itemName: "",
  lotQty: "",
  unit: "EA",
  sample: "",
};

function toDraft(inspection: Inspection): Draft {
  return {
    sample: String(Number(inspection.sampleQty)),
    note: inspection.note ?? "",
    entries: Object.fromEntries(
      (inspection.values ?? []).map((v) => [
        v.specItemId,
        {
          measured:
            v.measuredValue === null ? "" : String(Number(v.measuredValue)),
          passed: v.passValue,
          defect: v.defectTypeId === null ? "" : String(v.defectTypeId),
        },
      ]),
    ),
  };
}

export function Inspections() {
  const { fail } = useSession();
  const [params, setParams] = useSearchParams();
  const [filters, setFilters] = useState({ status: "", result: "" });
  const [rows, setRows] = useState<Inspection[]>();
  const [defects, setDefects] = useState<DefectType[]>([]);
  const [error, setError] = useState<unknown>();
  const [reload, setReload] = useState(0);
  const [panel, setPanel] = useState<
    { kind: "edit" | "view"; id: number } | { kind: "manual" } | null
  >(null);
  const [detail, setDetail] = useState<Inspection>();
  const [draft, setDraft] = useState<Draft>();
  const [initial, setInitial] = useState<Draft>();
  const [manual, setManual] = useState<Manual>(EMPTY_MANUAL);
  const [done, setDone] = useState<{ text: string; holdId?: number }>();
  const {
    send,
    pending,
    error: saveError,
    setError: setSaveError,
  } = useSend(() => setReload((n) => n + 1));
  const dirty =
    (panel?.kind === "edit" &&
      JSON.stringify(draft) !== JSON.stringify(initial)) ||
    (panel?.kind === "manual" &&
      JSON.stringify(manual) !== JSON.stringify(EMPTY_MANUAL));
  const guard = useDiscardGuard(dirty);

  const handle = (e: unknown) => {
    setError(e);
    if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
  };
  useEffect(() => {
    const controller = new AbortController();
    const query = new URLSearchParams(
      Object.entries(filters).filter(([, v]) => v),
    );
    api<Inspection[]>(`${QMS}/inspections?${query}`, {
      signal: controller.signal,
    })
      .then((r) => !controller.signal.aborted && setRows(r.data))
      .catch((e) => !controller.signal.aborted && handle(e));
    return () => controller.abort();
  }, [filters, reload]);
  useEffect(() => {
    api<DefectType[]>(`${QMS}/defect-types`)
      .then((r) => setDefects(r.data.filter((d) => d.isActive)))
      .catch(() => undefined);
  }, [reload]);
  // Q-03에서 넘어오면(?open=id) 그 검사를, ?manual=1이면 직접 입력 패널을 연다.
  useEffect(() => {
    const open = Number(params.get("open"));
    if (open) void openInspection(open);
    else if (params.get("manual")) openManual();
    if (open || params.get("manual")) setParams({}, { replace: true });
  }, []);

  if (moduleOff(error)) return <ModuleOff />;
  const errors = fieldErrors(saveError);

  async function openInspection(id: number) {
    setSaveError(undefined);
    try {
      const r = await api<Inspection>(`${QMS}/inspections/${id}`);
      setDetail(r.data);
      const d = toDraft(r.data);
      setDraft(d);
      setInitial(d);
      setPanel({ kind: r.data.status === "draft" ? "edit" : "view", id });
    } catch (e) {
      handle(e);
    }
  }
  function openManual() {
    setManual(EMPTY_MANUAL);
    setSaveError(undefined);
    setPanel({ kind: "manual" });
  }
  function close() {
    setPanel(null);
    setDetail(undefined);
  }

  function body(d: Draft, values: InspectionValue[]) {
    return {
      sampleQty: d.sample,
      note: d.note || null,
      values: values.map((v) => {
        const e = d.entries[v.specItemId];
        const judged = previewJudgement(v, e.measured, e.passed);
        return v.method === "RANGE"
          ? {
              specItemId: v.specItemId,
              measuredValue:
                e.measured.trim() === "" ? null : e.measured.trim(),
              defectTypeId:
                judged === "FAIL" && e.defect ? Number(e.defect) : null,
            }
          : {
              specItemId: v.specItemId,
              passValue: e.passed,
              defectTypeId:
                judged === "FAIL" && e.defect ? Number(e.defect) : null,
            };
      }),
    };
  }
  async function save(confirm: boolean) {
    if (!detail || !draft || pending) return;
    const saved = await send<Inspection>(
      `/inspections/${detail.id}`,
      "PATCH",
      body(draft, detail.values ?? []),
    );
    if (!saved) return;
    const fresh = toDraft(saved);
    setDetail(saved);
    setDraft(fresh);
    setInitial(fresh);
    if (!confirm) {
      setDone({ text: `${saved.inspectionNo} 임시 저장했습니다.` });
      return;
    }
    const confirmed = await send<Inspection>(
      `/inspections/${detail.id}/confirm`,
      "POST",
    );
    if (!confirmed) return;
    close();
    setDone(
      confirmed.result === "FAIL"
        ? {
            text: `${confirmed.inspectionNo} 불합격 확정 · ${confirmed.lotNo} 품질 보류 ${confirmed.activeHold?.holdNo ?? ""}`,
            holdId: confirmed.activeHold?.id,
          }
        : { text: `${confirmed.inspectionNo} 합격 확정` },
    );
  }
  async function submitManual(event: FormEvent) {
    event.preventDefault();
    const created = await send<Inspection>("/inspections", "POST", {
      source: "MANUAL",
      lotNo: manual.lotNo.trim(),
      itemCode: manual.itemCode.trim().toUpperCase(),
      itemName: manual.itemName.trim(),
      lotQty: manual.lotQty.trim(),
      unit: manual.unit.trim(),
      sampleQty: manual.sample.trim(),
    });
    if (created) void openInspection(created.id);
  }
  async function reinspect(id: number) {
    const created = await send<Inspection>(
      `/inspections/${id}/reinspect`,
      "POST",
    );
    if (created) void openInspection(created.id);
  }

  const columns: Column<Inspection>[] = [
    { key: "inspectionNo", label: "검사 번호" },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <button
          type="button"
          className="link-button"
          aria-pressed={panel !== null && "id" in panel && panel.id === r.id}
          onClick={() => guard.guard(() => void openInspection(r.id))}
        >
          {r.status === "draft" ? "입력" : "상세"}
        </button>
      ),
    },
    {
      key: "lotNo",
      label: "LOT",
      render: (r) => (
        <>
          {r.lotNo} <SpcBadge signal={r.spcSignal} />
        </>
      ),
    },
    {
      key: "itemCode",
      label: "품목",
      render: (r) => `${r.itemCode} ${r.itemName}`,
    },
    {
      key: "sampleQty",
      label: "표본",
      render: (r) => `${num(r.sampleQty)} ${r.unit}`,
    },
    {
      key: "result",
      label: "판정",
      render: (r) => <ResultBadge result={r.result} />,
    },
    {
      key: "source",
      label: "출처",
      render: (r) => SOURCE[r.source],
    },
    { key: "inspectedOn", label: "검사일" },
  ];

  const values = detail?.values ?? [];
  const readOnlyRows = (
    <div className="table-scroll">
      <table>
        <caption>{detail?.inspectionNo} 측정값</caption>
        <thead>
          <tr>
            <th scope="col">항목</th>
            <th scope="col">기준</th>
            <th scope="col" className="num">
              측정
            </th>
            <th scope="col">판정</th>
            <th scope="col">불량 유형</th>
          </tr>
        </thead>
        <tbody>
          {values.map((v) => (
            <tr key={v.specItemId}>
              <td>{v.name}</td>
              <td className="wrap">{limitText(v)}</td>
              <td className="num">
                {v.method === "RANGE"
                  ? v.measuredValue === null
                    ? "—"
                    : num(v.measuredValue, 4)
                  : v.passValue === null
                    ? "—"
                    : v.passValue
                      ? "합"
                      : "부"}
              </td>
              <td>
                {v.judgement ? <ResultBadge result={v.judgement} /> : "—"}
              </td>
              <td>{v.defectCode ? `${v.defectCode} ${v.defectName}` : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  return (
    <div className="page-fill">
      <PageTitle
        id="Q-04"
        title="검사"
        subtitle="검사 기준 대비 측정값을 입력하고 합격·불합격을 확정합니다"
        help="qms/q-04"
        actions={
          <button
            type="button"
            aria-pressed={panel?.kind === "manual"}
            onClick={() => guard.guard(openManual)}
          >
            직접 입력으로 검사
          </button>
        }
      />
      {done && (
        <p role="status">
          {done.text}
          {done.holdId && (
            <>
              {" "}
              <Link className="text-link" to="/qms/holds">
                품질 보류 보기 →
              </Link>
            </>
          )}
        </p>
      )}
      {!panel && (
        <ErrorNotice
          error={Object.keys(errors).length ? undefined : saveError}
        />
      )}
      <ErrorNotice error={error} retry={() => setReload((n) => n + 1)} />
      {!rows ? (
        !error && <Loading delay={300} />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <div className="filter-bar">
              <label>
                상태
                <select
                  value={filters.status}
                  onChange={(e) =>
                    setFilters({ ...filters, status: e.target.value })
                  }
                >
                  <option value="">전체</option>
                  <option value="draft">작성 중</option>
                  <option value="confirmed">확정</option>
                </select>
              </label>
              <label>
                판정
                <select
                  value={filters.result}
                  onChange={(e) =>
                    setFilters({ ...filters, result: e.target.value })
                  }
                >
                  <option value="">전체</option>
                  <option value="PASS">합격</option>
                  <option value="FAIL">불합격</option>
                </select>
              </label>
            </div>
            <DataTable
              rows={rows}
              columns={columns}
              caption="검사 목록"
              offset={0}
              total={rows.length}
              limit={rows.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="아직 검사가 없습니다. 검사 대기에서 MES LOT을 골라 검사를 시작하세요."
                  to="/qms/pending"
                  action="검사 대기로"
                />
              }
            />
          </section>

          {panel?.kind === "edit" && detail && draft && (
            <FormPanel
              wide
              key={`edit-${detail.id}`}
              title={`${detail.inspectionNo} · ${detail.lotNo} 검사`}
              guard={guard}
              onClose={close}
              onSubmit={(e) => {
                e.preventDefault();
                void save(true);
              }}
              actions={
                <>
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    확정
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    disabled={pending}
                    onClick={() => void save(false)}
                  >
                    임시 저장
                  </button>
                  <button
                    type="button"
                    className="link-button"
                    onClick={() => guard.guard(close)}
                  >
                    닫기
                  </button>
                  <p className="muted">
                    확정하면 수정할 수 없습니다. 잘못 확정했으면 재검사하세요.
                  </p>
                </>
              }
            >
              <ErrorNotice
                error={Object.keys(errors).length ? undefined : saveError}
              />
              <p className="muted">
                {detail.itemCode} {detail.itemName} · 기준 v{detail.specVersion}{" "}
                · LOT 수량 {num(detail.lotQty)} {detail.unit}
                {detail.reinspectionOfId && " · 재검사"}
              </p>
              {detail.activeHold && (
                <p className="notice" role="note">
                  이 LOT은 품질 보류 중입니다({detail.activeHold.holdNo}).
                  재검사에 합격하면 보류를 풀 수 있습니다.
                </p>
              )}
              <div className="field-row">
                <Field
                  label={`표본 수량 (${detail.unit})`}
                  inputMode="decimal"
                  value={draft.sample}
                  required
                  error={errors.sampleQty}
                  onChange={(e) =>
                    setDraft({ ...draft, sample: e.target.value })
                  }
                />
              </div>
              <div className="table-scroll section-block">
                <table>
                  <caption>측정값 입력</caption>
                  <thead>
                    <tr>
                      <th scope="col">항목</th>
                      <th scope="col">기준</th>
                      <th scope="col">측정·판정 입력</th>
                      <th scope="col">판정</th>
                      <th scope="col">불량 유형</th>
                    </tr>
                  </thead>
                  <tbody>
                    {values.map((v) => {
                      const e = draft.entries[v.specItemId];
                      const set = (patch: Partial<Entry>) =>
                        setDraft({
                          ...draft,
                          entries: {
                            ...draft.entries,
                            [v.specItemId]: { ...e, ...patch },
                          },
                        });
                      const judged = previewJudgement(v, e.measured, e.passed);
                      const itemError = errors[`values.${v.seq}`];
                      const defectError =
                        errors[`values.${v.seq}.defectTypeId`];
                      return (
                        <tr key={v.specItemId}>
                          <td>
                            {v.name}
                            {!v.isRequired && (
                              <small className="muted"> 선택</small>
                            )}
                          </td>
                          <td className="wrap">{limitText(v)}</td>
                          <td>
                            {v.method === "RANGE" ? (
                              <input
                                aria-label={`${v.name} 측정값`}
                                inputMode="decimal"
                                value={e.measured}
                                aria-invalid={!!itemError}
                                onChange={(ev) =>
                                  set({ measured: ev.target.value })
                                }
                              />
                            ) : (
                              <span
                                className="row-actions"
                                role="radiogroup"
                                aria-label={`${v.name} 판정`}
                              >
                                {([true, false] as const).map((ok) => (
                                  <label
                                    key={String(ok)}
                                    className="inline-check"
                                  >
                                    <input
                                      type="radio"
                                      name={`pf-${v.specItemId}`}
                                      checked={e.passed === ok}
                                      onChange={() => set({ passed: ok })}
                                    />
                                    {ok ? "합격" : "불합격"}
                                  </label>
                                ))}
                              </span>
                            )}
                            {itemError && (
                              <small className="field-error">{itemError}</small>
                            )}
                          </td>
                          <td>
                            {judged ? <ResultBadge result={judged} /> : "—"}
                          </td>
                          <td>
                            {judged === "FAIL" ? (
                              <>
                                <select
                                  aria-label={`${v.name} 불량 유형`}
                                  value={e.defect}
                                  aria-invalid={!!defectError}
                                  onChange={(ev) =>
                                    set({ defect: ev.target.value })
                                  }
                                >
                                  <option value="">선택</option>
                                  {defects.map((d) => (
                                    <option key={d.id} value={d.id}>
                                      {d.code} {d.name}
                                    </option>
                                  ))}
                                </select>
                                {defectError && (
                                  <small className="field-error">
                                    {defectError}
                                  </small>
                                )}
                              </>
                            ) : (
                              "—"
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <Field
                label="메모"
                value={draft.note}
                maxLength={300}
                onChange={(e) => setDraft({ ...draft, note: e.target.value })}
              />
              {defects.length === 0 && (
                <p className="muted">
                  불량 유형이 없습니다. 불합격 항목이 있으면{" "}
                  <Link to="/qms/defect-types">불량 유형</Link>을 먼저
                  등록하세요.
                </p>
              )}
            </FormPanel>
          )}

          {panel?.kind === "view" && detail && (
            <DetailPanel
              wide
              key={`view-${detail.id}`}
              title={`${detail.inspectionNo} · ${detail.lotNo}`}
              onClose={close}
              actions={
                <button
                  type="button"
                  className="secondary"
                  disabled={pending}
                  onClick={() => void reinspect(detail.id)}
                >
                  재검사
                </button>
              }
            >
              <ErrorNotice error={saveError} />
              <p>
                <ResultBadge result={detail.result} /> {detail.itemCode}{" "}
                {detail.itemName} · 기준 v{detail.specVersion} · 표본{" "}
                {num(detail.sampleQty)} / {num(detail.lotQty)} {detail.unit} ·{" "}
                {detail.inspectedOn}
              </p>
              {detail.activeHold && (
                <p className="notice" role="note">
                  품질 보류 중 · {detail.activeHold.holdNo}{" "}
                  <Link className="text-link" to="/qms/holds">
                    보류 보기 →
                  </Link>
                </p>
              )}
              {readOnlyRows}
              {detail.note && <p className="muted">메모: {detail.note}</p>}
            </DetailPanel>
          )}

          {panel?.kind === "manual" && (
            <FormPanel
              title="직접 입력 검사"
              guard={guard}
              onClose={close}
              onSubmit={(e) => void submitManual(e)}
              actions={
                <>
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    검사 만들기
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => guard.guard(close)}
                  >
                    취소
                  </button>
                </>
              }
            >
              <ErrorNotice
                error={Object.keys(errors).length ? undefined : saveError}
              />
              <p className="muted" role="note">
                MES를 쓰지 않거나 외부 LOT을 검사할 때 씁니다. 입력한 값이 검사
                기록에 그대로 남습니다.
              </p>
              <Field
                label="LOT 번호"
                value={manual.lotNo}
                required
                maxLength={50}
                error={errors.lotNo}
                onChange={(e) =>
                  setManual({ ...manual, lotNo: e.target.value })
                }
              />
              <div className="field-row">
                <Field
                  label="품목 코드"
                  value={manual.itemCode}
                  required
                  maxLength={40}
                  error={errors.itemCode}
                  onChange={(e) =>
                    setManual({
                      ...manual,
                      itemCode: e.target.value.toUpperCase(),
                    })
                  }
                />
                <Field
                  label="품목명"
                  value={manual.itemName}
                  required
                  maxLength={100}
                  error={errors.itemName}
                  onChange={(e) =>
                    setManual({ ...manual, itemName: e.target.value })
                  }
                />
              </div>
              <div className="field-row">
                <Field
                  label="LOT 수량"
                  inputMode="decimal"
                  value={manual.lotQty}
                  required
                  error={errors.lotQty}
                  onChange={(e) =>
                    setManual({ ...manual, lotQty: e.target.value })
                  }
                />
                <Field
                  label="단위"
                  value={manual.unit}
                  required
                  maxLength={10}
                  error={errors.unit}
                  onChange={(e) =>
                    setManual({ ...manual, unit: e.target.value })
                  }
                />
              </div>
              <Field
                label="표본 수량"
                inputMode="decimal"
                value={manual.sample}
                required
                error={errors.sampleQty}
                onChange={(e) =>
                  setManual({ ...manual, sample: e.target.value })
                }
              />
            </FormPanel>
          )}
        </div>
      )}
    </div>
  );
}
