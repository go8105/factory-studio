// B-04 공조 운전 — 공조기 목록 → 상세(DetailPanel wide: 상태·설정값·명령·최근 명령) → 설정값 폼 (UI-03 V 패턴, M-04 기준).
// 명령은 TX-B1: 거부도 이력으로 남고 사유를 알린다. 수동 운전은 다음 스케줄 경계까지 유지된다(FS-025 D22).
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
  RevealAnchor,
  useDiscardGuard,
  type Column,
} from "../shared/components";
import {
  AdvanceControl,
  BEMS,
  commandText,
  fieldErrors,
  ModuleOff,
  moduleOff,
  nextBoundary,
  num,
  REJECT_LABEL,
  SETPOINT_LABEL,
  SETPOINT_RANGE,
  SOURCE_LABEL,
  STATE_LABEL,
  time,
  useGet,
  useLists,
  useSend,
  type Clock,
  type Command,
  type Mode,
  type Overview,
  type SetpointKind,
  type UnitDetail,
  type Zone,
} from "./common";

type Row = Overview & { temp?: string; co2?: string; cool: string };
type Draft = { kind: SetpointKind; value: string; note: string };
const EMPTY: Draft = { kind: "COOL_TEMP", value: "", note: "" };

export function Hvac() {
  const { data, error, reload } = useLists<[Overview[], Zone[]]>([
    "/hvac-overview",
    "/zones",
  ]);
  const clock = useGet<Clock>("/simulation/clock");
  const [openId, setOpenId] = useState<number | null>(null);
  const [form, setForm] = useState(false);
  const [detail, setDetail] = useState<UnitDetail>();
  const [tick, setTick] = useState(0);
  const [mode, setMode] = useState<Mode>("COOL");
  const [message, setMessage] = useState("");
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const guard = useDiscardGuard(
    form && JSON.stringify(draft) !== JSON.stringify(EMPTY),
  );
  const refresh = () => {
    reload();
    clock.reload();
    setTick((n) => n + 1);
  };
  const { send, pending, error: saveError, setError } = useSend(refresh);
  useEffect(() => {
    if (!openId) return;
    void api<UnitDetail>(`${BEMS}/hvac-units/${openId}/detail`)
      .then((r) => setDetail(r.data))
      .catch(setError);
  }, [openId, tick]);
  if (moduleOff(error)) return <ModuleOff />;
  const [overview, zones] = data ?? [[], []];
  const units: Row[] = overview.map((u) => ({
    ...u,
    temp: u.environment.TEMP,
    co2: u.environment.CO2,
    cool: u.setpoints.COOL_TEMP,
  }));
  const zoneName = (id: number) => zones.find((z) => z.id === id)?.name ?? "—";
  const unit = detail?.id === openId ? detail : undefined;
  const errors = fieldErrors(saveError);

  async function command(body: Record<string, unknown>) {
    if (!unit) return undefined;
    setMessage("");
    const r = await send<Command>("/commands", "POST", {
      zoneId: unit.zoneId,
      hvacUnitId: unit.id,
      ...body,
    });
    if (!r) return undefined;
    if (r.result === "REJECTED")
      setMessage(
        `거부됨: ${commandText(r)} — ${REJECT_LABEL[r.rejectReason ?? ""] ?? r.rejectReason}. 이력에 남겼습니다.`,
      );
    else {
      const boundary =
        clock.data && unit.schedule.length
          ? nextBoundary(unit.schedule, clock.data.next)
          : null;
      setMessage(
        `적용: ${commandText(r)}. ` +
          (r.command === "SET_SETPOINT"
            ? "다음 1시간 진행부터 반영됩니다."
            : boundary
              ? `다음 스케줄 경계(${time(boundary)})까지 수동 운전, 이후 스케줄로 돌아갑니다.`
              : "스케줄이 없어 다음 명령 전까지 수동 운전을 유지합니다."),
      );
    }
    return r;
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    const r = await command({
      command: "SET_SETPOINT",
      setpointKind: draft.kind,
      value: draft.value,
      note: draft.note || undefined,
    });
    // 거부면 폼에 남아 값을 고칠 수 있게 한다(거부도 이력에는 남았다).
    if (r?.result === "APPLIED") {
      setForm(false);
      setDraft(EMPTY);
    }
  }
  function open(id: number) {
    guard.guard(() => {
      setOpenId(id);
      setForm(false);
      setMessage("");
      setError(undefined);
    });
  }

  const columns: Column<Row>[] = [
    { key: "code", label: "공조기" },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <button
          type="button"
          className="link-button"
          aria-pressed={openId === r.id}
          onClick={() => open(r.id)}
        >
          상세
        </button>
      ),
    },
    { key: "zoneId", label: "구역", render: (r) => zoneName(r.zoneId) },
    {
      key: "state",
      label: "상태",
      render: (r) =>
        r.isActive ? (
          STATE_LABEL[r.state]
        ) : (
          <Badge tone="warning">사용 안 함</Badge>
        ),
    },
    {
      key: "controlSource",
      label: "운전 출처",
      render: (r) =>
        r.controlSource === "MANUAL" ? (
          <Badge tone="warning">수동</Badge>
        ) : (
          SOURCE_LABEL.SCHEDULE
        ),
    },
    { key: "temp", label: "실내 온도", render: (r) => num(r.temp) },
    { key: "cool", label: "냉방 설정", render: (r) => num(r.cool) },
    { key: "co2", label: "CO₂", render: (r) => num(r.co2, 0) },
    {
      key: "lastPower",
      label: "전력(최근 1h)",
      render: (r) => (r.lastPower == null ? "—" : `${num(r.lastPower, 2)} kWh`),
    },
  ];
  const [low, high, unitLabel] = SETPOINT_RANGE[draft.kind];

  return (
    <div className="page-fill">
      <PageTitle
        id="B-04"
        title="공조 운전"
        subtitle="공조기 상태·설정값을 바꾸고 1시간씩 진행해 결과를 봅니다"
        help="bems/b-04"
        actions={<AdvanceControl choices={[1, 3, 6]} onDone={refresh} />}
      />
      <ErrorNotice error={error} retry={reload} />
      {!data ? (
        !error && <Loading />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <DataTable
              rows={units}
              columns={columns}
              caption="공조기 목록"
              offset={0}
              total={units.length}
              limit={units.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="공조기가 없습니다. 구역·계측에서 공조기를 등록하세요."
                  to="/bems/zones"
                  action="구역·계측으로"
                />
              }
            />
          </section>
          <RevealAnchor when={openId} />
          {openId && !form && (
            <DetailPanel
              wide
              title={unit ? `${unit.code} ${unit.name}` : "공조기"}
              guard={guard}
              onClose={() => setOpenId(null)}
            >
              {!unit ? (
                <Loading />
              ) : (
                <>
                  <p>
                    상태 <strong>{STATE_LABEL[unit.state]}</strong> ·{" "}
                    {SOURCE_LABEL[unit.controlSource]} 운전 · 정격{" "}
                    {num(unit.ratedKw)} kW · {zoneName(unit.zoneId)}
                  </p>
                  <p className="muted">
                    설정값{" "}
                    {(Object.keys(SETPOINT_LABEL) as SetpointKind[])
                      .map(
                        (k) =>
                          `${SETPOINT_LABEL[k]} ${num(unit.setpoints[k])}${SETPOINT_RANGE[k][2]}`,
                      )
                      .join(" · ")}
                  </p>
                  <div className="row-actions">
                    <button
                      type="button"
                      className="secondary"
                      disabled={pending}
                      onClick={() =>
                        void command({
                          command:
                            unit.state === "OFF" ? "POWER_ON" : "POWER_OFF",
                        })
                      }
                    >
                      {unit.state === "OFF" ? "전원 켜기" : "전원 끄기"}
                    </button>
                    <select
                      aria-label="모드"
                      value={mode}
                      onChange={(e) => setMode(e.target.value as Mode)}
                    >
                      {(["COOL", "HEAT", "FAN"] as Mode[]).map((m) => (
                        <option key={m} value={m}>
                          {STATE_LABEL[m]}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      className="secondary"
                      disabled={pending}
                      onClick={() =>
                        void command({ command: "SET_MODE", mode })
                      }
                    >
                      모드 적용
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setDraft(EMPTY);
                        setError(undefined);
                        setForm(true);
                      }}
                    >
                      설정값 변경
                    </button>
                  </div>
                  <p role="status">{message}</p>
                  <ErrorNotice error={saveError} />
                  <div className="table-scroll">
                    <table>
                      <caption>최근 명령</caption>
                      <thead>
                        <tr>
                          <th scope="col">시각</th>
                          <th scope="col">명령</th>
                          <th scope="col">출처</th>
                          <th scope="col">결과</th>
                        </tr>
                      </thead>
                      <tbody>
                        {unit.commands.map((c) => (
                          <tr key={c.id}>
                            <td>{time(c.requestedAt)}</td>
                            <td>{commandText(c)}</td>
                            <td>{SOURCE_LABEL[c.source]}</td>
                            <td>
                              {c.result === "APPLIED" ? (
                                "적용"
                              ) : (
                                <Badge tone="warning">
                                  거부 ·{" "}
                                  {REJECT_LABEL[c.rejectReason ?? ""] ??
                                    c.rejectReason}
                                </Badge>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {!unit.commands.length && (
                    <p className="muted">명령 이력이 없습니다.</p>
                  )}
                </>
              )}
            </DetailPanel>
          )}
          {openId && form && unit && (
            <FormPanel
              title={`${unit.code} 설정값 변경`}
              guard={guard}
              onClose={() => setForm(false)}
              onSubmit={(e) => void submit(e)}
              actions={
                <>
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    적용
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => guard.guard(() => setForm(false))}
                  >
                    취소
                  </button>
                </>
              }
            >
              <ErrorNotice
                error={Object.keys(errors).length ? undefined : saveError}
              />
              <fieldset className="field">
                <legend>항목</legend>
                {(Object.keys(SETPOINT_LABEL) as SetpointKind[]).map((k) => (
                  <label key={k} className="inline-check">
                    <input
                      type="radio"
                      name="setpoint-kind"
                      checked={draft.kind === k}
                      onChange={() => setDraft({ ...draft, kind: k })}
                    />
                    {SETPOINT_LABEL[k]} (현재 {num(unit.setpoints[k])}
                    {SETPOINT_RANGE[k][2]})
                  </label>
                ))}
              </fieldset>
              <Field
                label={`값 (${unitLabel}, 허용 ${low}~${high})`}
                value={draft.value}
                required
                inputMode="decimal"
                pattern="-?\d{1,6}(\.\d{1,2})?"
                error={errors.value}
                onChange={(e) => setDraft({ ...draft, value: e.target.value })}
              />
              <Field
                label="메모"
                value={draft.note}
                maxLength={300}
                onChange={(e) => setDraft({ ...draft, note: e.target.value })}
              />
              <p role="status">{message}</p>
              <p className="muted">
                범위 밖이거나 냉방이 난방보다 2℃ 이상 높지 않으면 거부되고
                이력에 남습니다.
              </p>
            </FormPanel>
          )}
        </div>
      )}
    </div>
  );
}
