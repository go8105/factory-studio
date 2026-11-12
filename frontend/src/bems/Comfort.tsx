// B-10 쾌적도 — 구역×지표 쾌적 시간 비율(조회 계산) + 쾌적 기준 관리 (UI-03 L+S 패턴).
// 비율은 저장하지 않는다. "근무 시간만" 기준은 그 구역 운전 스케줄이 켜져 있도록 잡힌 시각을 쓴다.
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import {
  Badge,
  DataTable,
  EmptyState,
  ErrorNotice,
  Field,
  FormPanel,
  Loading,
  PageTitle,
  ScreenIntro,
  useDiscardGuard,
  type Column,
} from "../shared/components";
import {
  COMFORT_REASON,
  fieldErrors,
  KIND_LABEL,
  METRICS,
  METRIC_LABEL,
  ModuleOff,
  moduleOff,
  num,
  UNIT,
  useGet,
  useLists,
  useSend,
  type ComfortRow,
  type ComfortStandard,
  type Metric,
  type Zone,
} from "./common";

type Tab = "ratio" | "standards";
type Draft = {
  zoneKind: Zone["kind"];
  metric: Metric;
  low: string;
  high: string;
  occupiedOnly: boolean;
};
const EMPTY: Draft = {
  zoneKind: "OFFICE",
  metric: "TEMP",
  low: "",
  high: "",
  occupiedOnly: true,
};
type Row = ComfortRow & { id: string };

const range = (low: string | null, high: string | null, unit: string) =>
  low && high
    ? `${num(low)} ~ ${num(high)} ${unit}`
    : low
      ? `${num(low)} ${unit} 이상`
      : `${num(high)} ${unit} 이하`;

export function Comfort() {
  const [tab, setTab] = useState<Tab>("ratio");
  const comfort = useGet<{ from: string; to: string; rows: ComfortRow[] }>(
    "/comfort",
  );
  const lists = useLists<[ComfortStandard[]]>(["/comfort-standards"]);
  const [editing, setEditing] = useState<ComfortStandard | "new" | null>(null);
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [initial, setInitial] = useState<Draft>(EMPTY);
  const refresh = () => {
    comfort.reload();
    lists.reload();
  };
  const { send, pending, error: saveError, setError } = useSend(refresh);
  const guard = useDiscardGuard(
    !!editing && JSON.stringify(draft) !== JSON.stringify(initial),
  );
  if (moduleOff(comfort.error) || moduleOff(lists.error)) return <ModuleOff />;
  const standards = lists.data?.[0] ?? [];
  const errors = fieldErrors(saveError);
  const rows: Row[] = (comfort.data?.rows ?? []).map((r) => ({
    ...r,
    id: `${r.zoneId}:${r.metric}`,
  }));

  function open(standard: ComfortStandard | "new") {
    const values: Draft =
      standard === "new"
        ? EMPTY
        : {
            zoneKind: standard.zoneKind,
            metric: standard.metric,
            low: standard.low ?? "",
            high: standard.high ?? "",
            occupiedOnly: standard.occupiedOnly,
          };
    guard.guard(() => {
      setEditing(standard);
      setDraft(values);
      setInitial(values);
      setError(undefined);
    });
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!editing) return;
    const body = {
      low: draft.low || null,
      high: draft.high || null,
      occupiedOnly: draft.occupiedOnly,
    };
    const saved =
      editing === "new"
        ? await send("/comfort-standards", "POST", {
            zoneKind: draft.zoneKind,
            metric: draft.metric,
            ...body,
          })
        : await send(`/comfort-standards/${editing.id}`, "PATCH", body);
    if (saved) setEditing(null);
  }

  const ratioColumns: Column<Row>[] = [
    { key: "zoneName", label: "구역" },
    {
      key: "metric",
      label: "지표",
      render: (r) => METRIC_LABEL[r.metric],
    },
    {
      key: "low",
      label: "쾌적 범위",
      render: (r) => range(r.low, r.high, r.unit),
    },
    {
      key: "occupiedOnly",
      label: "세는 시간",
      render: (r) => (r.occupiedOnly ? "근무 시간만" : "전체"),
    },
    { key: "hours", label: "관측 시간", render: (r) => `${r.hours}h` },
    {
      key: "insideHours",
      label: "범위 안",
      render: (r) => `${r.insideHours}h`,
    },
    {
      key: "ratio",
      label: "쾌적 시간 비율",
      render: (r) =>
        r.ratio === null ? (
          <Badge tone="warning">모름</Badge>
        ) : (
          <strong>{r.ratio}%</strong>
        ),
    },
    {
      key: "reason",
      label: "비고",
      render: (r) => (r.reason ? COMFORT_REASON[r.reason] : "—"),
    },
  ];
  const standardColumns: Column<ComfortStandard>[] = [
    {
      key: "zoneKind",
      label: "구역 용도",
      render: (s) => KIND_LABEL[s.zoneKind],
    },
    { key: "metric", label: "지표", render: (s) => METRIC_LABEL[s.metric] },
    {
      key: "low",
      label: "쾌적 범위",
      render: (s) => range(s.low, s.high, UNIT[s.metric]),
    },
    {
      key: "occupiedOnly",
      label: "세는 시간",
      render: (s) => (s.occupiedOnly ? "근무 시간만" : "전체"),
    },
    {
      key: "id",
      label: "관리",
      render: (s) => (
        <button
          type="button"
          className="link-button"
          aria-pressed={editing !== "new" && editing?.id === s.id}
          onClick={() => open(s)}
        >
          수정
        </button>
      ),
    },
  ];

  return (
    <div className="page-fill">
      <PageTitle
        id="B-10"
        title="쾌적도"
        subtitle="구역 용도별 쾌적 범위 안에 머문 시간의 비율입니다. 저장하지 않고 관측에서 계산합니다"
        help="bems/b-10"
        actions={
          tab === "standards" && (
            <button
              type="button"
              aria-pressed={editing === "new"}
              onClick={() => open("new")}
            >
              기준 등록
            </button>
          )
        }
      />
      <ScreenIntro>
        비율 = 쾌적 범위 안 관측 시간 ÷ 센 관측 시간. &quot;근무 시간만&quot;
        기준은 그 구역의 <Link to="/bems/schedules">운전 스케줄</Link>이 켜져
        있도록 잡힌 시각만 셉니다. 스케줄이 없으면 근무 시간을 알 수 없어 0%가
        아니라 <strong>모름</strong>입니다.
      </ScreenIntro>
      <div className="tabs" role="tablist">
        {(
          [
            ["ratio", "쾌적 시간 비율"],
            ["standards", "쾌적 기준"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            aria-pressed={tab === key}
            className={tab === key ? "active" : ""}
            onClick={() => guard.guard(() => setTab(key))}
          >
            {label}
          </button>
        ))}
      </div>
      {!editing && <ErrorNotice error={saveError} />}
      <ErrorNotice error={comfort.error ?? lists.error} retry={refresh} />
      {tab === "ratio" ? (
        !comfort.data ? (
          !comfort.error && <Loading />
        ) : (
          <DataTable
            rows={rows}
            columns={ratioColumns}
            caption={`쾌적 시간 비율 (${comfort.data.from} ~ ${comfort.data.to})`}
            offset={0}
            total={rows.length}
            limit={rows.length || 1}
            onPage={() => undefined}
            empty={
              <EmptyState
                reason="쾌적 기준이 없습니다. 구역 용도별 기준을 먼저 등록하세요."
                action="쾌적 기준으로"
                onAction={() => setTab("standards")}
              />
            }
          />
        )
      ) : (
        <div className="split-view fill">
          <section className="fill">
            {!lists.data ? (
              !lists.error && <Loading />
            ) : (
              <DataTable
                rows={standards}
                columns={standardColumns}
                caption="쾌적 기준"
                offset={0}
                total={standards.length}
                limit={standards.length || 1}
                onPage={() => undefined}
                empty={
                  <EmptyState
                    reason="쾌적 기준이 없습니다."
                    action="기준 등록"
                    onAction={() => open("new")}
                  />
                }
              />
            )}
          </section>
          {editing && (
            <FormPanel
              key={editing === "new" ? "new" : editing.id}
              title={
                editing === "new"
                  ? "쾌적 기준 등록"
                  : `${KIND_LABEL[editing.zoneKind]} ${METRIC_LABEL[editing.metric]} 수정`
              }
              guard={guard}
              onClose={() => setEditing(null)}
              onSubmit={(e) => void submit(e)}
              actions={
                <>
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    {editing === "new" ? "등록" : "저장"}
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => guard.guard(() => setEditing(null))}
                  >
                    취소
                  </button>
                </>
              }
            >
              <ErrorNotice
                error={Object.keys(errors).length ? undefined : saveError}
              />
              <div className="field">
                <label htmlFor="bems-comfort-kind">구역 용도</label>
                <select
                  id="bems-comfort-kind"
                  value={draft.zoneKind}
                  disabled={editing !== "new"}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      zoneKind: e.target.value as Zone["kind"],
                    })
                  }
                >
                  {(Object.keys(KIND_LABEL) as Zone["kind"][]).map((k) => (
                    <option key={k} value={k}>
                      {KIND_LABEL[k]}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="bems-comfort-metric">지표</label>
                <select
                  id="bems-comfort-metric"
                  value={draft.metric}
                  disabled={editing !== "new"}
                  aria-invalid={!!errors.metric}
                  onChange={(e) =>
                    setDraft({ ...draft, metric: e.target.value as Metric })
                  }
                >
                  {METRICS.map((m) => (
                    <option key={m} value={m}>
                      {METRIC_LABEL[m]} ({UNIT[m]})
                    </option>
                  ))}
                </select>
                {errors.metric && <small>{errors.metric}</small>}
              </div>
              <Field
                label={`하한 (${UNIT[draft.metric]}, 선택)`}
                value={draft.low}
                inputMode="decimal"
                pattern="\d{1,8}(\.\d{1,2})?"
                error={errors.low}
                onChange={(e) => setDraft({ ...draft, low: e.target.value })}
              />
              <Field
                label={`상한 (${UNIT[draft.metric]}, 선택)`}
                value={draft.high}
                inputMode="decimal"
                pattern="\d{1,8}(\.\d{1,2})?"
                error={errors.high}
                onChange={(e) => setDraft({ ...draft, high: e.target.value })}
              />
              <label className="inline-check">
                <input
                  type="checkbox"
                  checked={draft.occupiedOnly}
                  onChange={(e) =>
                    setDraft({ ...draft, occupiedOnly: e.target.checked })
                  }
                />
                근무 시간만 센다
              </label>
              <p className="muted">
                하한과 상한 중 하나는 입력합니다. 미세먼지처럼 건강에 관한
                지표는 근무 시간 밖도 함께 보는 편이 맞습니다.
              </p>
            </FormPanel>
          )}
        </div>
      )}
    </div>
  );
}
