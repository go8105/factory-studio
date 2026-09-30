// S-04 측정 입력 — MES 공정 실행 선택 → 부분군 5값 입력(TX-S1) (UI-02 V 패턴 + FormPanel).
// MES 교차 조회 시연 화면: 공정 실행 목록은 MES에서 읽고, SPC는 MES 데이터를 바꾸지 않는다.
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import {
  Badge,
  DataTable,
  EmptyState,
  ErrorNotice,
  FormPanel,
  Loading,
  PageTitle,
  useDiscardGuard,
  type Column,
} from "../shared/components";
import { ApiError } from "../shared/api";
import {
  CharacteristicSelect,
  fieldErrors,
  ModuleOff,
  moduleOff,
  num,
  RULE_LABEL,
  spec,
  time,
  toIso,
  toLocal,
  useCharacteristic,
  useGet,
  useSend,
  type Characteristic,
} from "./common";

type Run = {
  id: number;
  lotNo: string;
  itemCode: string;
  processCode: string;
  equipmentCode: string;
  startedAt: string;
  endedAt: string | null;
  subgroupCount: number;
};
type Recorded = {
  xbar: string;
  r: string;
  signals: { chart: "XBAR" | "R"; rule: 1 | 2 | 3; value: string }[];
};

const sourceOff = (e: unknown) =>
  e instanceof ApiError && e.error.details?.reason === "SOURCE_MODULE_DISABLED";

function stats(values: string[]) {
  const nums = values.filter((v) => v.trim() !== "").map(Number);
  if (nums.length !== 5 || nums.some(Number.isNaN)) return null;
  return {
    xbar: nums.reduce((a, b) => a + b, 0) / 5,
    r: Math.max(...nums) - Math.min(...nums),
  };
}

export function Measure() {
  const list = useGet<Characteristic[]>("/characteristics");
  const { current, select, query } = useCharacteristic(list.data);
  const runs = useGet<Omit<Run, "id">[]>(
    current ? `/runs?characteristicId=${current.id}` : null,
  );
  const [run, setRun] = useState<Run | null>(null);
  const [at, setAt] = useState("");
  const [values, setValues] = useState(["", "", "", "", ""]);
  const [note, setNote] = useState("");
  const [result, setResult] = useState<Recorded>();
  const { send, pending, error, setError } = useSend(() => runs.reload());
  const guard = useDiscardGuard(!!run && values.some((v) => v !== ""));
  if (moduleOff(list.error)) return <ModuleOff />;
  const rows = (runs.data ?? []).map((r, i) => ({ ...r, id: i + 1 }));
  const errors = fieldErrors(error);
  const live = stats(values);
  const c = current;

  function open(r: Run) {
    guard.guard(() => {
      const upper = r.endedAt ? Date.parse(r.endedAt) : Date.now();
      setRun(r);
      setAt(toLocal(new Date(Math.min(upper, Date.now())).toISOString()));
      setValues(["", "", "", "", ""]);
      setNote("");
      setError(undefined);
    });
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!run || !c) return;
    const r = await send<Recorded>("/subgroups", "POST", {
      characteristicId: c.id,
      lotNo: run.lotNo,
      measuredAt: toIso(at),
      values,
      note: note || undefined,
    });
    if (r) {
      setResult(r);
      setValues(["", "", "", "", ""]);
      setRun(null);
    }
  }
  const outside = (v: string) =>
    !!c &&
    v !== "" &&
    ((c.lsl != null && Number(v) < Number(c.lsl)) ||
      (c.usl != null && Number(v) > Number(c.usl)));

  const columns: Column<Run>[] = [
    { key: "lotNo", label: "LOT" },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <button
          type="button"
          className="link-button"
          aria-pressed={run?.lotNo === r.lotNo}
          onClick={() => open(r)}
        >
          측정 입력
        </button>
      ),
    },
    { key: "equipmentCode", label: "설비" },
    { key: "startedAt", label: "시작", render: (r) => time(r.startedAt) },
    {
      key: "endedAt",
      label: "종료",
      render: (r) =>
        r.endedAt ? time(r.endedAt) : <Badge tone="warning">진행 중</Badge>,
    },
    { key: "subgroupCount", label: "기록된 부분군" },
  ];

  return (
    <div className="page-fill">
      <PageTitle
        id="S-04"
        title="측정 입력"
        subtitle="공정 실행 한 건을 골라 한 시각에 연속 측정한 값 5개를 기록합니다"
        help="spc/s-04"
      />
      <p role="note" className="muted">
        공정 실행 목록은 MES에서 읽어 옵니다. SPC는 MES 데이터를 바꾸지
        않습니다.
      </p>
      <ErrorNotice
        error={list.error ?? (sourceOff(runs.error) ? undefined : runs.error)}
        retry={() => runs.reload()}
      />
      <p role="status">
        {result &&
          (result.signals.length ? (
            <>
              부분군을 기록했습니다. X̄ {num(result.xbar, 4)} —{" "}
              {result.signals
                .map(
                  (s) => `${s.chart === "R" ? "R " : ""}${RULE_LABEL[s.rule]}`,
                )
                .join(", ")}{" "}
              이상이 생겼습니다.{" "}
              <Link to={`/spc/signals${query}`}>이상·조치 →</Link>
            </>
          ) : (
            <>
              부분군을 기록했습니다. X̄ {num(result.xbar, 4)} — 이상 없음.{" "}
              <Link to={`/spc/chart${query}`}>관리도 →</Link>
            </>
          ))}
      </p>
      {!list.data ? (
        !list.error && <Loading />
      ) : !list.data.length || !c ? (
        <EmptyState
          reason="관리 특성이 없습니다."
          to="/spc/characteristics"
          action="관리 특성 등록"
        />
      ) : (
        <>
          <div className="filter-bar">
            <CharacteristicSelect
              list={list.data}
              value={c.id}
              onChange={(id) => guard.guard(() => select(id))}
            />
            <span className="muted">규격 {spec(c)}</span>
          </div>
          {sourceOff(runs.error) ? (
            <EmptyState
              reason="MES를 사용하지 않도록 설정했습니다. 관리도·공정능력·이상 조치는 그대로 쓸 수 있습니다."
              to={`/spc/chart${query}`}
              action="관리도로"
            />
          ) : !runs.data ? (
            !runs.error && <Loading />
          ) : (
            <div className="split-view fill">
              <section className="fill">
                <DataTable
                  rows={rows}
                  columns={columns}
                  caption="MES 공정 실행(최근 30일)"
                  offset={0}
                  total={rows.length}
                  limit={rows.length || 1}
                  onPage={() => undefined}
                  empty={
                    <EmptyState
                      reason="이 품목·공정으로 시작된 공정 실행이 없습니다."
                      to="/mes"
                      action="MES로"
                    />
                  }
                />
              </section>
              {run && (
                <FormPanel
                  title="측정 입력"
                  guard={guard}
                  onClose={() => setRun(null)}
                  onSubmit={(e) => void submit(e)}
                  actions={
                    <>
                      <button
                        type="submit"
                        disabled={pending}
                        aria-busy={pending}
                      >
                        기록
                      </button>
                      <button
                        type="button"
                        className="secondary"
                        onClick={() => guard.guard(() => setRun(null))}
                      >
                        취소
                      </button>
                    </>
                  }
                >
                  <p className="muted">
                    {run.lotNo} · {run.equipmentCode} · 규격 {spec(c)}
                  </p>
                  <ErrorNotice
                    error={Object.keys(errors).length ? undefined : error}
                  />
                  <div className="field">
                    <label htmlFor="spc-measured-at">측정 시각</label>
                    <input
                      id="spc-measured-at"
                      type="datetime-local"
                      value={at}
                      required
                      aria-invalid={!!errors.measuredAt}
                      aria-describedby={
                        errors.measuredAt ? "spc-measured-at-error" : undefined
                      }
                      onChange={(e) => setAt(e.target.value)}
                    />
                    {errors.measuredAt && (
                      <small id="spc-measured-at-error">
                        {errors.measuredAt}
                      </small>
                    )}
                  </div>
                  <fieldset className="spc-values">
                    <legend>측정값 5개 ({c.unit})</legend>
                    {values.map((v, i) => (
                      <label key={i}>
                        값 {i + 1}
                        <input
                          aria-label={`값 ${i + 1}`}
                          value={v}
                          required
                          inputMode="decimal"
                          pattern="-?\d{1,8}(\.\d{1,4})?"
                          aria-invalid={!!errors[`values.${i + 1}`]}
                          onChange={(e) =>
                            setValues(
                              values.map((x, j) =>
                                j === i ? e.target.value : x,
                              ),
                            )
                          }
                        />
                        {outside(v) && (
                          <small className="spc-outside">규격 밖</small>
                        )}
                        {errors[`values.${i + 1}`] && (
                          <small>{errors[`values.${i + 1}`]}</small>
                        )}
                      </label>
                    ))}
                  </fieldset>
                  <p className="muted" aria-live="polite">
                    {live
                      ? `X̄ ${num(live.xbar, 4)} · R ${num(live.r, 4)}`
                      : "값 5개를 모두 넣으면 X̄·R을 계산합니다."}
                  </p>
                  <div className="field">
                    <label htmlFor="spc-note">메모(선택)</label>
                    <input
                      id="spc-note"
                      value={note}
                      maxLength={300}
                      onChange={(e) => setNote(e.target.value)}
                    />
                  </div>
                </FormPanel>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
