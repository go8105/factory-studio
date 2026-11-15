// B-11 건물 에너지 — 월별 공용 사용량·원단위(EUI)·목표 달성률 + 목표 관리 (UI-03 D+S 패턴).
// 원단위는 저장하지 않고 관측에서 계산한다. 달성률 = 실적 ÷ 목표(FEMS와 같은 규칙, 100% 이하면 목표 이내).
import { useState, type FormEvent } from "react";
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
  KIND_LABEL,
  ModuleOff,
  moduleOff,
  num,
  percent,
  useGet,
  useLists,
  useSend,
  type BuildingEnergy,
  type BuildingEnergyZone,
  type EnergyTarget,
  type Zone,
} from "./common";

type Tab = "energy" | "targets";
type Draft = { targetMonth: string; zoneId: string; targetKwh: string };

const thisMonth = () => new Date().toISOString().slice(0, 7);
const achievementBadge = (v: string | null) =>
  v === null ? (
    <Badge tone="warning">목표 없음</Badge>
  ) : Number(v) <= 1 ? (
    <Badge>{percent(v)}</Badge>
  ) : (
    <Badge tone="issue">{percent(v)}</Badge>
  );

export function Energy() {
  const [tab, setTab] = useState<Tab>("energy");
  const [month, setMonth] = useState(thisMonth());
  const energy = useGet<BuildingEnergy>(`/building-energy?month=${month}`);
  const lists = useLists<[EnergyTarget[], Zone[]]>([
    "/energy-targets",
    "/zones",
  ]);
  const [editing, setEditing] = useState<EnergyTarget | "new" | null>(null);
  const [draft, setDraft] = useState<Draft>({
    targetMonth: month,
    zoneId: "",
    targetKwh: "",
  });
  const [initial, setInitial] = useState<Draft>(draft);
  const refresh = () => {
    energy.reload();
    lists.reload();
  };
  const { send, pending, error: saveError, setError } = useSend(refresh);
  const guard = useDiscardGuard(
    !!editing && JSON.stringify(draft) !== JSON.stringify(initial),
  );
  if (moduleOff(energy.error) || moduleOff(lists.error)) return <ModuleOff />;
  const [targets, zones] = lists.data ?? [[], []];
  const zoneName = (id: number | null) =>
    id === null ? "건물 전체" : (zones.find((z) => z.id === id)?.name ?? "—");

  function open(target: EnergyTarget | "new") {
    const values: Draft =
      target === "new"
        ? { targetMonth: month, zoneId: "", targetKwh: "" }
        : {
            targetMonth: target.targetMonth,
            zoneId: target.zoneId ? String(target.zoneId) : "",
            targetKwh: target.targetKwh,
          };
    guard.guard(() => {
      setEditing(target);
      setDraft(values);
      setInitial(values);
      setError(undefined);
    });
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!editing) return;
    const saved =
      editing === "new"
        ? await send("/energy-targets", "POST", {
            targetMonth: draft.targetMonth,
            zoneId: draft.zoneId ? Number(draft.zoneId) : null,
            targetKwh: draft.targetKwh,
          })
        : await send(`/energy-targets/${editing.id}`, "PATCH", {
            targetKwh: draft.targetKwh,
          });
    if (saved) setEditing(null);
  }

  const zoneColumns: Column<BuildingEnergyZone & { id: number }>[] = [
    { key: "zoneName", label: "구역" },
    { key: "kind", label: "용도", render: (z) => KIND_LABEL[z.kind] },
    {
      key: "floorAreaM2",
      label: "면적 ㎡",
      render: (z) => (z.floorAreaM2 ? num(z.floorAreaM2, 0) : "—"),
    },
    { key: "kwh", label: "사용량 kWh", render: (z) => num(z.kwh, 0) },
    {
      key: "euiKwhPerM2",
      label: "원단위 kWh/㎡",
      render: (z) => (z.euiKwhPerM2 ? num(z.euiKwhPerM2, 4) : "—"),
    },
    {
      key: "targetKwh",
      label: "목표 kWh",
      render: (z) => (z.targetKwh ? num(z.targetKwh, 0) : "—"),
    },
    {
      key: "achievement",
      label: "달성률",
      render: (z) => achievementBadge(z.achievement),
    },
  ];
  const targetColumns: Column<EnergyTarget>[] = [
    { key: "targetMonth", label: "목표 월" },
    { key: "zoneId", label: "범위", render: (t) => zoneName(t.zoneId) },
    { key: "targetKwh", label: "목표 kWh", render: (t) => num(t.targetKwh, 0) },
    {
      key: "id",
      label: "관리",
      render: (t) => (
        <button
          type="button"
          className="link-button"
          aria-pressed={editing !== "new" && editing?.id === t.id}
          onClick={() => open(t)}
        >
          수정
        </button>
      ),
    },
  ];
  const data = energy.data;

  return (
    <div className="page-fill">
      <PageTitle
        id="B-11"
        title="건물 에너지"
        subtitle="월별 공용 사용량과 면적당 원단위, 목표 대비 실적입니다"
        help="bems/b-11"
        actions={
          <>
            <Field
              label="조회 월"
              type="month"
              value={month}
              onChange={(e) => setMonth(e.target.value || thisMonth())}
            />
            {tab === "targets" && (
              <button
                type="button"
                aria-pressed={editing === "new"}
                onClick={() => open("new")}
              >
                목표 등록
              </button>
            )}
          </>
        }
      />
      <ScreenIntro>
        원단위(EUI) = 공용 사용량 ÷ 연면적. 저장하지 않고 관측에서 계산합니다.
        달성률 = 실적 ÷ 목표이고 <strong>100% 이하면 목표 이내</strong>입니다.
        연면적이나 목표가 없으면 0이 아니라 <strong>—</strong>로 둡니다.
      </ScreenIntro>
      <div className="tabs" role="tablist">
        {(
          [
            ["energy", "사용량·원단위"],
            ["targets", "목표 관리"],
          ] as const
        ).map(([k, label]) => (
          <button
            key={k}
            type="button"
            aria-pressed={tab === k}
            className={tab === k ? "active" : ""}
            onClick={() => guard.guard(() => setTab(k))}
          >
            {label}
          </button>
        ))}
      </div>
      {!editing && <ErrorNotice error={saveError} />}
      <ErrorNotice error={energy.error ?? lists.error} retry={refresh} />
      {tab === "energy" ? (
        !data ? (
          !energy.error && <Loading />
        ) : (
          <>
            <div className="kpi-row">
              <article className="kpi">
                <h2>공용 사용량</h2>
                <p className="kpi-value">{num(data.totalKwh, 0)} kWh</p>
                <p className="muted">{data.month}</p>
              </article>
              <article className="kpi">
                <h2>연면적</h2>
                <p className="kpi-value">{num(data.grossAreaM2, 0)} ㎡</p>
                <p className="muted">건물 합계</p>
              </article>
              <article className="kpi">
                <h2>원단위</h2>
                <p className="kpi-value">
                  {data.euiKwhPerM2 ? num(data.euiKwhPerM2, 4) : "—"}
                </p>
                <p className="muted">kWh/㎡</p>
              </article>
              <article className="kpi">
                <h2>목표 달성률</h2>
                <p className="kpi-value">{percent(data.achievement)}</p>
                <p className="muted">
                  {data.targetKwh
                    ? `목표 ${num(data.targetKwh, 0)} kWh`
                    : "목표 없음"}
                </p>
              </article>
            </div>
            <DataTable
              rows={data.zones.map((z) => ({ ...z, id: z.zoneId }))}
              columns={zoneColumns}
              caption={`${data.month} 구역별 사용량·원단위`}
              offset={0}
              total={data.zones.length}
              limit={data.zones.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="이 달에 공용 계측이 없습니다. 다른 달을 고르거나 1시간 진행으로 관측을 만드세요."
                  to="/bems/hvac"
                  action="공조 운전으로"
                />
              }
            />
          </>
        )
      ) : (
        <div className="split-view fill">
          <section className="fill">
            {!lists.data ? (
              !lists.error && <Loading />
            ) : (
              <DataTable
                rows={targets}
                columns={targetColumns}
                caption="건물 에너지 목표"
                offset={0}
                total={targets.length}
                limit={targets.length || 1}
                onPage={() => undefined}
                empty={
                  <EmptyState
                    reason="목표가 없습니다. 달과 범위를 정해 등록하세요."
                    action="목표 등록"
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
                  ? "건물 에너지 목표 등록"
                  : `${editing.targetMonth} ${zoneName(editing.zoneId)} 목표 수정`
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
              <Field
                label="목표 월"
                type="month"
                value={draft.targetMonth}
                required
                disabled={editing !== "new"}
                onChange={(e) =>
                  setDraft({ ...draft, targetMonth: e.target.value })
                }
              />
              <div className="field">
                <label htmlFor="bems-target-zone">범위</label>
                <select
                  id="bems-target-zone"
                  value={draft.zoneId}
                  disabled={editing !== "new"}
                  onChange={(e) =>
                    setDraft({ ...draft, zoneId: e.target.value })
                  }
                >
                  <option value="">건물 전체</option>
                  {zones.map((z) => (
                    <option key={z.id} value={z.id}>
                      {z.name}
                    </option>
                  ))}
                </select>
              </div>
              <Field
                label="목표 kWh"
                value={draft.targetKwh}
                required
                inputMode="decimal"
                pattern="\d{1,12}(\.\d{1,2})?"
                onChange={(e) =>
                  setDraft({ ...draft, targetKwh: e.target.value })
                }
              />
              <p className="muted">
                달·범위마다 목표는 하나입니다. 건물 전체 목표가 B-13 월간
                보고서의 달성률이 됩니다.
              </p>
            </FormPanel>
          )}
        </div>
      )}
    </div>
  );
}
