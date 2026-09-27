// Q-05 품질 보류 — 목록 + 보류 상세(DetailPanel wide) + 해제 처분(FormPanel, 닫으면 상세로).
// 보류는 QMS 기록이다. MES 패킹을 막지 않고 MES 화면에는 배지로만 보인다(FS-023 D10).
import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useSession } from "../app/session";
import { api, ApiError } from "../shared/api";
import {
  DataTable,
  DetailPanel,
  EmptyState,
  ErrorNotice,
  FormPanel,
  Loading,
  PageTitle,
  useDiscardGuard,
  type Column,
} from "../shared/components";
import {
  DISPOSITION,
  fieldErrors,
  HoldBadge,
  limitText,
  ModuleOff,
  moduleOff,
  num,
  QMS,
  ResultBadge,
  time,
  useSend,
  type Hold,
  type Inspection,
} from "./common";

type Detail = Hold & {
  reinspections: Inspection[];
  failedItems: {
    seq: number;
    name: string;
    measuredValue: string | null;
    passValue: boolean | null;
    lowerLimit: string | null;
    upperLimit: string | null;
    unit: string | null;
    defectCode: string | null;
    defectName: string | null;
  }[];
};
type Release = {
  disposition: keyof typeof DISPOSITION;
  inspectionId: string;
  reason: string;
};
const EMPTY: Release = {
  disposition: "REINSPECTED",
  inspectionId: "",
  reason: "",
};

export function Holds() {
  const { fail } = useSession();
  const [status, setStatus] = useState("held");
  const [rows, setRows] = useState<Hold[]>();
  const [error, setError] = useState<unknown>();
  const [reload, setReload] = useState(0);
  const [panel, setPanel] = useState<{
    kind: "detail" | "release";
    id: number;
  } | null>(null);
  const [detail, setDetail] = useState<Detail>();
  const [release, setRelease] = useState<Release>(EMPTY);
  const [releaseInitial, setReleaseInitial] = useState<Release>(EMPTY);
  const [done, setDone] = useState("");
  const {
    send,
    pending,
    error: saveError,
    setError: setSaveError,
  } = useSend(() => setReload((n) => n + 1));
  const guard = useDiscardGuard(
    panel?.kind === "release" &&
      JSON.stringify(release) !== JSON.stringify(releaseInitial),
  );

  useEffect(() => {
    const controller = new AbortController();
    api<Hold[]>(`${QMS}/holds${status ? `?status=${status}` : ""}`, {
      signal: controller.signal,
    })
      .then((r) => !controller.signal.aborted && setRows(r.data))
      .catch((e) => {
        if (controller.signal.aborted) return;
        setError(e);
        if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
      });
    return () => controller.abort();
  }, [status, reload]);

  if (moduleOff(error)) return <ModuleOff />;
  const errors = fieldErrors(saveError);

  async function openDetail(id: number) {
    setSaveError(undefined);
    const r = await api<Detail>(`${QMS}/holds/${id}`);
    setDetail(r.data);
    setPanel({ kind: "detail", id });
  }
  function openRelease() {
    if (!detail) return;
    const passed = detail.reinspections.find((i) => i.result === "PASS");
    // 합격 재검사가 없으면 재검사 합격은 고를 수 없으므로 특채를 기본으로 둔다.
    const values: Release = passed
      ? { ...EMPTY, inspectionId: String(passed.id) }
      : { ...EMPTY, disposition: "CONCESSION" };
    setRelease(values);
    setReleaseInitial(values);
    setSaveError(undefined);
    setPanel({ kind: "release", id: detail.id });
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!detail) return;
    const saved = await send<Detail>(`/holds/${detail.id}/release`, "POST", {
      disposition: release.disposition,
      releaseInspectionId:
        release.disposition === "REINSPECTED" && release.inspectionId
          ? Number(release.inspectionId)
          : null,
      reason: release.reason.trim() || null,
    });
    if (saved) {
      setPanel(null);
      setDetail(undefined);
      setDone(`${saved.holdNo} 해제 · ${DISPOSITION[saved.disposition!]}`);
    }
  }

  const passedReinspections =
    detail?.reinspections.filter((i) => i.result === "PASS") ?? [];
  const columns: Column<Hold>[] = [
    { key: "holdNo", label: "보류 번호" },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <button
          type="button"
          className="link-button"
          aria-pressed={panel?.id === r.id}
          onClick={() => guard.guard(() => void openDetail(r.id))}
        >
          상세
        </button>
      ),
    },
    { key: "lotNo", label: "LOT" },
    { key: "itemCode", label: "품목" },
    { key: "inspectionNo", label: "원인 검사" },
    { key: "heldAt", label: "보류", render: (r) => time(r.heldAt) },
    { key: "status", label: "상태", render: (r) => <HoldBadge hold={r} /> },
  ];

  return (
    <div className="page-fill">
      <PageTitle
        id="Q-05"
        title="품질 보류"
        subtitle="불합격 LOT의 보류와 처분(재검사 합격·특채·폐기 판정)을 기록합니다"
        help="qms/q-05"
      />
      <p className="muted" role="note">
        보류는 QMS 기록입니다. MES 패킹을 막지 않으며, MES 패킹·LOT 화면에
        &quot;QMS 보류&quot; 배지로 표시됩니다. 폐기 판정도 MES 수량을 바꾸지
        않습니다.
      </p>
      {done && <p role="status">{done}</p>}
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
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                >
                  <option value="held">보류 중</option>
                  <option value="released">해제</option>
                  <option value="">전체</option>
                </select>
              </label>
            </div>
            <DataTable
              rows={rows}
              columns={columns}
              caption="품질 보류 목록"
              offset={0}
              total={rows.length}
              limit={rows.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason={
                    status === "held"
                      ? "보류 중인 LOT이 없습니다."
                      : "보류 기록이 없습니다."
                  }
                  to="/qms/inspections"
                  action="검사로"
                />
              }
            />
          </section>

          {panel?.kind === "detail" && detail && (
            <DetailPanel
              wide
              key={`detail-${detail.id}`}
              title={`${detail.lotNo} 보류 · ${detail.holdNo}`}
              onClose={() => setPanel(null)}
              actions={
                detail.status === "held" && (
                  <button type="button" onClick={openRelease}>
                    해제 처분
                  </button>
                )
              }
            >
              <p>
                <HoldBadge hold={detail} /> {detail.itemCode} · 원인 검사{" "}
                {detail.inspectionNo} · 보류 {time(detail.heldAt)}
                {detail.releasedAt && ` · 해제 ${time(detail.releasedAt)}`}
              </p>
              {detail.releaseReason && (
                <p className="muted">해제 사유: {detail.releaseReason}</p>
              )}
              <div className="section-block">
                <div className="table-scroll">
                  <table>
                    <caption>불합격 항목</caption>
                    <thead>
                      <tr>
                        <th scope="col">항목</th>
                        <th scope="col">기준</th>
                        <th scope="col" className="num">
                          측정
                        </th>
                        <th scope="col">불량 유형</th>
                      </tr>
                    </thead>
                    <tbody>
                      {detail.failedItems.map((f) => (
                        <tr key={f.seq}>
                          <td>{f.name}</td>
                          <td className="wrap">
                            {limitText({
                              method:
                                f.passValue === null ? "RANGE" : "PASS_FAIL",
                              ...f,
                            })}
                          </td>
                          <td className="num">
                            {f.measuredValue !== null
                              ? num(f.measuredValue, 4)
                              : f.passValue === false
                                ? "부"
                                : "—"}
                          </td>
                          <td>
                            {f.defectCode
                              ? `${f.defectCode} ${f.defectName}`
                              : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
              <div className="section-block">
                <DataTable
                  rows={detail.reinspections}
                  columns={[
                    { key: "inspectionNo", label: "재검사" },
                    {
                      key: "result",
                      label: "판정",
                      render: (r) => <ResultBadge result={r.result} />,
                    },
                    { key: "inspectedOn", label: "검사일" },
                  ]}
                  caption="보류 이후 확정된 검사"
                  offset={0}
                  total={detail.reinspections.length}
                  limit={detail.reinspections.length || 1}
                  onPage={() => undefined}
                  empty={
                    <p className="muted">
                      보류 이후 확정된 검사가 없습니다.{" "}
                      <Link to="/qms/inspections">검사</Link>에서 원인 검사를
                      재검사하세요.
                    </p>
                  }
                />
              </div>
            </DetailPanel>
          )}

          {panel?.kind === "release" && detail && (
            <FormPanel
              key={`release-${detail.id}`}
              title={`${detail.lotNo} 보류 해제`}
              guard={guard}
              onClose={() => setPanel({ kind: "detail", id: detail.id })}
              onSubmit={(e) => void submit(e)}
              actions={
                <>
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    해제
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() =>
                      guard.guard(() =>
                        setPanel({ kind: "detail", id: detail.id }),
                      )
                    }
                  >
                    보류 상세로
                  </button>
                </>
              }
            >
              <ErrorNotice
                error={Object.keys(errors).length ? undefined : saveError}
              />
              <fieldset className="field">
                <legend>처분</legend>
                {(Object.keys(DISPOSITION) as (keyof typeof DISPOSITION)[]).map(
                  (d) => (
                    <label key={d} className="inline-check">
                      <input
                        type="radio"
                        name="disposition"
                        checked={release.disposition === d}
                        disabled={
                          d === "REINSPECTED" &&
                          passedReinspections.length === 0
                        }
                        onChange={() =>
                          setRelease({ ...release, disposition: d })
                        }
                      />
                      {DISPOSITION[d]}
                    </label>
                  ),
                )}
              </fieldset>
              {passedReinspections.length === 0 && (
                <p className="muted">
                  합격한 재검사가 없어 재검사 합격으로는 풀 수 없습니다.
                </p>
              )}
              {release.disposition === "REINSPECTED" ? (
                <div className="field">
                  <label htmlFor="release-inspection">합격 재검사</label>
                  <select
                    id="release-inspection"
                    value={release.inspectionId}
                    aria-invalid={!!errors.releaseInspectionId}
                    onChange={(e) =>
                      setRelease({ ...release, inspectionId: e.target.value })
                    }
                  >
                    <option value="">선택</option>
                    {passedReinspections.map((i) => (
                      <option key={i.id} value={i.id}>
                        {i.inspectionNo} · {i.inspectedOn}
                      </option>
                    ))}
                  </select>
                  {errors.releaseInspectionId && (
                    <small>{errors.releaseInspectionId}</small>
                  )}
                </div>
              ) : null}
              <div className="field">
                <label htmlFor="release-reason">
                  사유{release.disposition === "REINSPECTED" ? " (선택)" : ""}
                </label>
                <textarea
                  id="release-reason"
                  maxLength={300}
                  value={release.reason}
                  aria-invalid={!!errors.reason}
                  onChange={(e) =>
                    setRelease({ ...release, reason: e.target.value })
                  }
                />
                {errors.reason && <small>{errors.reason}</small>}
              </div>
            </FormPanel>
          )}
        </div>
      )}
    </div>
  );
}
