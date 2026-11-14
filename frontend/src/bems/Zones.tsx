// B-07 구역·계측 — 구역 목록 → 구역 상세(계측기·센서·공조기 세 표) → 각 폼 (UI-03 P 패턴, F-12 기준).
// 폼을 닫으면 구역 상세로 돌아간다. 용도·항목은 등록 뒤 바꾸지 않고, 쓰지 않는 행은 사용 안 함으로 둔다.
import { useState, type FormEvent, type ReactNode } from "react";
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
  KIND_LABEL,
  METRIC_LABEL,
  ModuleOff,
  moduleOff,
  num,
  STATE_LABEL,
  USAGE_LABEL,
  useGet,
  useLists,
  useSend,
  LIGHT_LABEL,
  type Building,
  type Departments,
  type HvacUnit,
  type LightingCircuit,
  type Meter,
  type Metric,
  type Sensor,
  type Zone,
} from "./common";

type Kind = "building" | "zone" | "meter" | "sensor" | "hvac" | "light";
const PATH: Record<Kind, string> = {
  building: "/buildings",
  zone: "/zones",
  meter: "/meters",
  sensor: "/sensors",
  hvac: "/hvac-units",
  light: "/lighting-circuits",
};
const TITLE: Record<Kind, string> = {
  building: "건물",
  zone: "구역",
  meter: "공용 계측기",
  sensor: "환경 센서",
  hvac: "공조기",
  light: "조명 회로",
};
/** 지하 B1·지상 3F·옥상 RF. 서버 schema.FLOOR와 같다. */
const FLOOR_PATTERN = "(B[1-9]\\d?|[1-9]\\d{0,2}F|RF)";
type Draft = {
  code: string;
  name: string;
  kind: Zone["kind"];
  floorAreaM2: string;
  usage: Meter["usage"];
  metric: Metric;
  meterId: string;
  ratedKw: string;
  isActive: boolean;
  floors: string;
  grossAreaM2: string;
  curtailPriority: string;
  buildingId: string;
  floorLabel: string;
  departmentCode: string;
};
const EMPTY: Draft = {
  code: "",
  name: "",
  kind: "OFFICE",
  floorAreaM2: "",
  usage: "LIGHTING",
  metric: "TEMP",
  meterId: "",
  ratedKw: "",
  isActive: true,
  floors: "",
  grossAreaM2: "",
  curtailPriority: "5",
  buildingId: "",
  floorLabel: "",
  departmentCode: "",
};
type Row = { id: number; code: string; isActive: boolean };
type FormRow = Row & {
  name?: string;
  kind?: Zone["kind"];
  floorAreaM2?: string | null;
  usage?: Meter["usage"];
  metric?: Metric;
  meterId?: number | null;
  ratedKw?: string;
  floors?: number;
  grossAreaM2?: string;
  curtailPriority?: number;
  buildingId?: number | null;
  floorLabel?: string | null;
  departmentCode?: string | null;
};
type Form = { kind: Kind; row: FormRow | null };

const active = (v: boolean) =>
  v ? "사용" : <Badge tone="warning">사용 안 함</Badge>;

function Sub<T extends Row>({
  caption,
  rows,
  head,
  cells,
  onEdit,
}: {
  caption: string;
  rows: T[];
  head: string[];
  cells: (r: T) => ReactNode[];
  onEdit: (r: T) => void;
}) {
  return (
    <>
      <h3>{caption}</h3>
      {rows.length ? (
        <div className="table-scroll">
          <table>
            <caption>{caption}</caption>
            <thead>
              <tr>
                <th scope="col">코드</th>
                {head.map((h) => (
                  <th key={h} scope="col">
                    {h}
                  </th>
                ))}
                <th scope="col">사용</th>
                <th scope="col">관리</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td>{r.code}</td>
                  {cells(r).map((c, i) => (
                    <td key={i}>{c}</td>
                  ))}
                  <td>{active(r.isActive)}</td>
                  <td>
                    <button
                      type="button"
                      className="link-button"
                      onClick={() => onEdit(r)}
                    >
                      수정
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="muted">{caption}가 없습니다.</p>
      )}
    </>
  );
}

export function Zones() {
  const { data, error, reload } = useLists<
    [Zone[], Meter[], Sensor[], HvacUnit[], Building[], LightingCircuit[]]
  >([
    "/zones",
    "/meters",
    "/sensors",
    "/hvac-units",
    "/buildings",
    "/lighting-circuits",
  ]);
  const departments = useGet<Departments>("/lookups/departments");
  const [zoneId, setZoneId] = useState<number | null>(null);
  const [form, setForm] = useState<Form | null>(null);
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [initial, setInitial] = useState<Draft>(EMPTY);
  const { send, pending, error: saveError, setError } = useSend(reload);
  const guard = useDiscardGuard(
    !!form && JSON.stringify(draft) !== JSON.stringify(initial),
  );
  if (moduleOff(error)) return <ModuleOff />;
  const [zones, meters, sensors, units, buildings, circuits] = data ?? [
    [],
    [],
    [],
    [],
    [],
    [],
  ];
  const zone = zones.find((z) => z.id === zoneId);
  const errors = fieldErrors(saveError);
  const inZone = <T extends { zoneId: number }>(rows: T[]) =>
    rows.filter((r) => r.zoneId === zoneId);
  const hvacMeters = inZone(meters).filter((m) => m.usage === "HVAC");
  const lightMeters = inZone(meters).filter((m) => m.usage === "LIGHTING");
  const buildingText = (z: Zone) => {
    const b = buildings.find((x) => x.id === z.buildingId);
    return b ? `${b.name}${z.floorLabel ? ` ${z.floorLabel}` : ""}` : "—";
  };
  const departmentText = (code: string | null) =>
    code
      ? (departments.data?.rows.find((d) => d.code === code)?.name ?? code)
      : "—";

  function openForm(kind: Kind, row: Form["row"]) {
    const values: Draft = row
      ? {
          ...EMPTY,
          code: row.code,
          name: row.name ?? "",
          kind: row.kind ?? EMPTY.kind,
          floorAreaM2: row.floorAreaM2 ?? "",
          usage: row.usage ?? EMPTY.usage,
          metric: row.metric ?? EMPTY.metric,
          meterId: row.meterId ? String(row.meterId) : "",
          ratedKw: row.ratedKw ?? "",
          isActive: row.isActive,
          floors: row.floors ? String(row.floors) : "",
          curtailPriority: row.curtailPriority
            ? String(row.curtailPriority)
            : EMPTY.curtailPriority,
          grossAreaM2: row.grossAreaM2 ?? "",
          buildingId: row.buildingId ? String(row.buildingId) : "",
          floorLabel: row.floorLabel ?? "",
          departmentCode: row.departmentCode ?? "",
        }
      : EMPTY;
    guard.guard(() => {
      setForm({ kind, row });
      setDraft(values);
      setInitial(values);
      setError(undefined);
    });
  }
  const closeForm = () => setForm(null);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!form) return;
    const { kind, row } = form;
    const code = draft.code.trim().toUpperCase();
    const place = {
      buildingId: draft.buildingId ? Number(draft.buildingId) : null,
      // 건물을 비우면 층 표기도 함께 비운다 — 서버가 건물 없는 층 표기를 거부한다.
      floorLabel: (draft.buildingId && draft.floorLabel) || null,
      departmentCode: draft.departmentCode || null,
    };
    const body: Record<Kind, Record<string, unknown>> = row
      ? {
          building: {
            name: draft.name,
            floors: Number(draft.floors),
            grossAreaM2: draft.grossAreaM2,
            isActive: draft.isActive,
          },
          zone: {
            name: draft.name,
            floorAreaM2: draft.floorAreaM2 || null,
            isActive: draft.isActive,
            ...place,
          },
          meter: { name: draft.name, isActive: draft.isActive },
          sensor: { isActive: draft.isActive },
          hvac: {
            name: draft.name,
            meterId: draft.meterId ? Number(draft.meterId) : null,
            ratedKw: draft.ratedKw,
            isActive: draft.isActive,
            curtailPriority: Number(draft.curtailPriority),
          },
          light: {
            name: draft.name,
            meterId: draft.meterId ? Number(draft.meterId) : null,
            ratedKw: draft.ratedKw,
            isActive: draft.isActive,
          },
        }
      : {
          building: {
            code,
            name: draft.name,
            floors: Number(draft.floors),
            grossAreaM2: draft.grossAreaM2,
          },
          zone: {
            code,
            name: draft.name,
            kind: draft.kind,
            floorAreaM2: draft.floorAreaM2 || undefined,
            ...place,
          },
          meter: { zoneId, code, name: draft.name, usage: draft.usage },
          sensor: { zoneId, code, metric: draft.metric },
          hvac: {
            zoneId,
            code,
            name: draft.name,
            meterId: draft.meterId ? Number(draft.meterId) : undefined,
            ratedKw: draft.ratedKw,
          },
          light: {
            zoneId,
            code,
            name: draft.name,
            meterId: draft.meterId ? Number(draft.meterId) : undefined,
            ratedKw: draft.ratedKw,
          },
        };
    const saved = row
      ? await send(`${PATH[kind]}/${row.id}`, "PATCH", body[kind])
      : await send(PATH[kind], "POST", body[kind]);
    if (saved) closeForm();
  }

  const columns: Column<Zone>[] = [
    { key: "code", label: "코드" },
    {
      key: "id",
      label: "관리",
      render: (z) => (
        <span className="row-actions">
          <button
            type="button"
            className="link-button"
            aria-pressed={zoneId === z.id && !form}
            onClick={() =>
              guard.guard(() => {
                setZoneId(z.id);
                setForm(null);
              })
            }
          >
            계측{" "}
            {meters.filter((m) => m.zoneId === z.id).length +
              sensors.filter((s) => s.zoneId === z.id).length}
          </button>
          <button
            type="button"
            className="link-button"
            onClick={() => openForm("zone", z)}
          >
            수정
          </button>
        </span>
      ),
    },
    { key: "name", label: "이름" },
    { key: "kind", label: "유형", render: (z) => KIND_LABEL[z.kind] },
    { key: "buildingId", label: "건물·층", render: buildingText },
    {
      key: "departmentCode",
      label: "사용 부서",
      render: (z) => departmentText(z.departmentCode),
    },
    {
      key: "floorAreaM2",
      label: "면적 ㎡",
      render: (z) => num(z.floorAreaM2, 2),
    },
    { key: "isActive", label: "사용", render: (z) => active(z.isActive) },
  ];
  const editing = !!form?.row;
  const k = form?.kind;

  return (
    <div className="page-fill">
      <PageTitle
        id="B-07"
        title="구역·계측"
        subtitle="건물·구역과 구역별 공용 계측기·환경 센서·공조기·조명 회로입니다. 이 계측은 FEMS와 따로 BEMS가 가집니다"
        help="bems/b-07"
        actions={
          <button
            type="button"
            aria-pressed={form?.kind === "zone" && !form.row}
            onClick={() => openForm("zone", null)}
          >
            구역 등록
          </button>
        }
      />
      {!form && !zone && <ErrorNotice error={saveError} />}
      <details className="bems-buildings">
        <summary>건물 {buildings.length}동</summary>
        <Sub
          caption="건물"
          rows={buildings}
          head={["이름", "층수", "연면적 ㎡"]}
          cells={(b) => [b.name, b.floors, num(b.grossAreaM2, 2)]}
          onEdit={(b) => openForm("building", b)}
        />
        <button
          type="button"
          className="secondary"
          aria-pressed={form?.kind === "building" && !form.row}
          onClick={() => openForm("building", null)}
        >
          건물 등록
        </button>
      </details>
      <ErrorNotice error={error} retry={reload} />
      {!data ? (
        !error && <Loading />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <DataTable
              rows={zones}
              columns={columns}
              caption="구역 목록"
              offset={0}
              total={zones.length}
              limit={zones.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="구역이 없습니다. 사무동·생산동 같은 구역을 먼저 등록하세요."
                  action="구역 등록"
                  onAction={() => openForm("zone", null)}
                />
              }
            />
          </section>
          {zone && !form && (
            <DetailPanel
              wide
              title={`${zone.name} 계측`}
              onClose={() => setZoneId(null)}
              actions={
                <>
                  <button type="button" onClick={() => openForm("meter", null)}>
                    계측기 추가
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => openForm("sensor", null)}
                  >
                    센서 추가
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => openForm("hvac", null)}
                  >
                    공조기 추가
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => openForm("light", null)}
                  >
                    조명 회로 추가
                  </button>
                </>
              }
            >
              <ErrorNotice error={saveError} />
              <Sub
                caption="공용 계측기"
                rows={inZone(meters)}
                head={["이름", "용도", "단위"]}
                cells={(m) => [m.name, USAGE_LABEL[m.usage], m.unit]}
                onEdit={(m) => openForm("meter", m)}
              />
              <Sub
                caption="환경 센서"
                rows={inZone(sensors)}
                head={["항목", "단위"]}
                cells={(s) => [METRIC_LABEL[s.metric], s.unit]}
                onEdit={(s) => openForm("sensor", s)}
              />
              <Sub
                caption="공조기"
                rows={inZone(units)}
                head={["이름", "정격 kW", "공조 계측기", "상태", "감축 순위"]}
                cells={(u) => [
                  u.name,
                  num(u.ratedKw),
                  meters.find((m) => m.id === u.meterId)?.code ?? "—",
                  STATE_LABEL[u.state],
                  u.curtailPriority,
                ]}
                onEdit={(u) => openForm("hvac", u)}
              />
              <Sub
                caption="조명 회로"
                rows={inZone(circuits)}
                head={["이름", "정격 kW", "조명 계측기", "상태"]}
                cells={(c) => [
                  c.name,
                  num(c.ratedKw, 2),
                  meters.find((m) => m.id === c.meterId)?.code ?? "—",
                  LIGHT_LABEL[c.state],
                ]}
                onEdit={(c) => openForm("light", c)}
              />
            </DetailPanel>
          )}
          {form && k && (
            <FormPanel
              key={`${k}:${form.row?.id ?? "new"}`}
              title={`${TITLE[k]} ${editing ? `${form.row?.code} 수정` : k === "zone" ? "등록" : `추가 · ${zone?.name ?? ""}`}`}
              guard={guard}
              onClose={closeForm}
              onSubmit={(e) => void submit(e)}
              actions={
                <>
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    {editing ? "저장" : "등록"}
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => guard.guard(closeForm)}
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
                disabled={editing}
                maxLength={20}
                pattern="[A-Z][A-Z0-9\-]{1,19}"
                title="영문 대문자로 시작하는 2~20자 (대문자·숫자·-)"
                error={errors.code}
                onChange={(e) =>
                  setDraft({ ...draft, code: e.target.value.toUpperCase() })
                }
              />
              {k !== "sensor" && (
                <Field
                  label="이름"
                  value={draft.name}
                  required
                  maxLength={100}
                  error={errors.name}
                  onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                />
              )}
              {k === "zone" && (
                <>
                  <div className="field">
                    <label htmlFor="bems-zone-kind">유형</label>
                    <select
                      id="bems-zone-kind"
                      value={draft.kind}
                      disabled={editing}
                      onChange={(e) =>
                        setDraft({
                          ...draft,
                          kind: e.target.value as Zone["kind"],
                        })
                      }
                    >
                      {(Object.keys(KIND_LABEL) as Zone["kind"][]).map((z) => (
                        <option key={z} value={z}>
                          {KIND_LABEL[z]}
                        </option>
                      ))}
                    </select>
                  </div>
                  <Field
                    label="면적 ㎡(선택)"
                    value={draft.floorAreaM2}
                    inputMode="decimal"
                    pattern="\d{1,8}(\.\d{1,2})?"
                    error={errors.floorAreaM2}
                    onChange={(e) =>
                      setDraft({ ...draft, floorAreaM2: e.target.value })
                    }
                  />
                  <div className="field">
                    <label htmlFor="bems-zone-building">건물(선택)</label>
                    <select
                      id="bems-zone-building"
                      value={draft.buildingId}
                      aria-invalid={!!errors.buildingId}
                      onChange={(e) =>
                        setDraft({
                          ...draft,
                          buildingId: e.target.value,
                          floorLabel: e.target.value ? draft.floorLabel : "",
                        })
                      }
                    >
                      <option value="">없음</option>
                      {buildings.map((b) => (
                        <option key={b.id} value={b.id}>
                          {b.code} {b.name}
                        </option>
                      ))}
                    </select>
                    {errors.buildingId && <small>{errors.buildingId}</small>}
                  </div>
                  <Field
                    label="층 표기(선택)"
                    value={draft.floorLabel}
                    disabled={!draft.buildingId}
                    maxLength={10}
                    pattern={FLOOR_PATTERN}
                    title="지하 B1 · 지상 3F · 옥상 RF"
                    error={errors.floorLabel}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        floorLabel: e.target.value.toUpperCase(),
                      })
                    }
                  />
                  <div className="field">
                    <label htmlFor="bems-zone-department">
                      사용 부서(선택)
                    </label>
                    {departments.data?.hrEnabled ? (
                      <select
                        id="bems-zone-department"
                        value={draft.departmentCode}
                        aria-invalid={!!errors.departmentCode}
                        onChange={(e) =>
                          setDraft({ ...draft, departmentCode: e.target.value })
                        }
                      >
                        <option value="">없음</option>
                        {departments.data.rows.map((d) => (
                          <option key={d.code} value={d.code}>
                            {d.code} {d.name}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        id="bems-zone-department"
                        value={draft.departmentCode}
                        maxLength={30}
                        aria-invalid={!!errors.departmentCode}
                        onChange={(e) =>
                          setDraft({ ...draft, departmentCode: e.target.value })
                        }
                      />
                    )}
                    {errors.departmentCode ? (
                      <small>{errors.departmentCode}</small>
                    ) : (
                      <small className="muted">
                        {departments.data?.hrEnabled
                          ? "부서 코드는 HR이 가집니다. 공용 비용 배분에 씁니다"
                          : "HR을 켜면 부서 목록에서 고를 수 있습니다"}
                      </small>
                    )}
                  </div>
                </>
              )}
              {k === "building" && (
                <>
                  <Field
                    label="층수"
                    value={draft.floors}
                    required
                    inputMode="numeric"
                    pattern="[1-9]\d{0,2}"
                    error={errors.floors}
                    onChange={(e) =>
                      setDraft({ ...draft, floors: e.target.value })
                    }
                  />
                  <Field
                    label="연면적 ㎡"
                    value={draft.grossAreaM2}
                    required
                    inputMode="decimal"
                    pattern="\d{1,10}(\.\d{1,2})?"
                    error={errors.grossAreaM2}
                    onChange={(e) =>
                      setDraft({ ...draft, grossAreaM2: e.target.value })
                    }
                  />
                </>
              )}
              {k === "meter" && (
                <div className="field">
                  <label htmlFor="bems-meter-usage">용도</label>
                  <select
                    id="bems-meter-usage"
                    value={draft.usage}
                    disabled={editing}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        usage: e.target.value as Meter["usage"],
                      })
                    }
                  >
                    {(Object.keys(USAGE_LABEL) as Meter["usage"][]).map((u) => (
                      <option key={u} value={u}>
                        {USAGE_LABEL[u]}
                      </option>
                    ))}
                  </select>
                  <small className="muted">
                    단위 kWh · 용도는 등록 뒤 바꾸지 않습니다
                  </small>
                </div>
              )}
              {k === "sensor" && (
                <div className="field">
                  <label htmlFor="bems-sensor-metric">항목</label>
                  <select
                    id="bems-sensor-metric"
                    value={draft.metric}
                    disabled={editing}
                    aria-invalid={!!errors.metric}
                    onChange={(e) =>
                      setDraft({ ...draft, metric: e.target.value as Metric })
                    }
                  >
                    {(Object.keys(METRIC_LABEL) as Metric[]).map((m) => (
                      <option key={m} value={m}>
                        {METRIC_LABEL[m]}
                      </option>
                    ))}
                  </select>
                  {errors.metric && <small>{errors.metric}</small>}
                </div>
              )}
              {(k === "hvac" || k === "light") && (
                <>
                  <div className="field">
                    <label htmlFor="bems-unit-meter">
                      {k === "hvac" ? "공조" : "조명"} 전력 계측기
                    </label>
                    <select
                      id="bems-unit-meter"
                      value={draft.meterId}
                      aria-invalid={!!errors.meterId}
                      onChange={(e) =>
                        setDraft({ ...draft, meterId: e.target.value })
                      }
                    >
                      <option value="">없음</option>
                      {(k === "hvac" ? hvacMeters : lightMeters).map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.code} {m.name}
                        </option>
                      ))}
                    </select>
                    {errors.meterId ? (
                      <small>{errors.meterId}</small>
                    ) : (
                      <small className="muted">
                        같은 구역의 {k === "hvac" ? "공조" : "조명"} 용도
                        계측기만 고를 수 있습니다
                      </small>
                    )}
                  </div>
                  <Field
                    label="정격 kW"
                    value={draft.ratedKw}
                    required
                    inputMode="decimal"
                    pattern="\d{1,8}(\.\d{1,2})?"
                    error={errors.ratedKw}
                    onChange={(e) =>
                      setDraft({ ...draft, ratedKw: e.target.value })
                    }
                  />
                  {k === "hvac" && editing && (
                    <Field
                      label="감축 우선순위 (1~9)"
                      value={draft.curtailPriority}
                      inputMode="numeric"
                      pattern="[1-9]"
                      title="피크 감축에서 낮은 번호부터 줄입니다"
                      error={errors.curtailPriority}
                      onChange={(e) =>
                        setDraft({ ...draft, curtailPriority: e.target.value })
                      }
                    />
                  )}
                </>
              )}
              {editing && (
                <label className="inline-check">
                  <input
                    type="checkbox"
                    checked={draft.isActive}
                    onChange={(e) =>
                      setDraft({ ...draft, isActive: e.target.checked })
                    }
                  />
                  사용
                </label>
              )}
            </FormPanel>
          )}
        </div>
      )}
    </div>
  );
}
