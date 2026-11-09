// B-05 운전 스케줄 — 공조기·조명 회로별 평일/주말/휴일 시간대를 넓은 행 편집 패널로 전체 교체 (UI-03 W 패턴, E-04 기준).
// 휴일은 core 공통 달력(P-08)을 본다. 휴일 시간대를 하나도 두지 않으면 그날은 주말 시간대를 따른다(DSN-16 Q1).
import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { api } from "../shared/api";
import {
  DataTable,
  EmptyState,
  ErrorNotice,
  FormPanel,
  Loading,
  PageTitle,
  ScreenIntro,
  useDiscardGuard,
  type Column,
} from "../shared/components";
import {
  BEMS,
  DAY_KINDS,
  DAY_LABEL,
  fieldErrors,
  ModuleOff,
  moduleOff,
  SLOT_LABEL,
  useLists,
  useSend,
  type CircuitDetail,
  type DayKind,
  type HvacUnit,
  type LightingCircuit,
  type Mode,
  type Slot,
  type UnitDetail,
} from "./common";

/** 스케줄 대상 한 줄. 공조기와 조명 회로는 경로와 고를 수 있는 모드만 다르다.
 *  공조기와 조명 회로의 id는 서로 겹치므로 표의 행 id는 "구분:id"로 만든다. */
type Row = {
  id: string;
  targetId: number;
  code: string;
  name: string;
  target: "hvac" | "light";
  targetLabel: string;
  weekday: string;
  weekend: string;
  holiday: string;
  slots: Slot[];
};
const PATH = { hvac: "/hvac-units", light: "/lighting-circuits" } as const;
const MODES: Record<Row["target"], (Mode | "ON")[]> = {
  hvac: ["COOL", "HEAT", "FAN"],
  light: ["ON"],
};
const HOURS = Array.from({ length: 25 }, (_, h) => h);
const summary = (slots: Slot[], day: DayKind) =>
  slots
    .filter((s) => s.dayKind === day)
    .map(
      (s) =>
        `${String(s.startHour).padStart(2, "0")}–${s.endHour} ${SLOT_LABEL[s.mode]}`,
    )
    .join(", ") || "—";

/** 24시간 막대 미리보기(평일·주말·휴일 세 줄). 모드는 무늬(글자)로도 구분한다. */
function Preview({ slots }: { slots: Slot[] }) {
  return (
    <figure className="bems-schedule-preview" aria-label="스케줄 미리보기">
      {DAY_KINDS.map((day) => (
        <div key={day} className="bems-schedule-row">
          <span>{DAY_LABEL[day]}</span>
          <div className="bems-schedule-track">
            {slots
              .filter((s) => s.dayKind === day && s.startHour < s.endHour)
              .map((s, i) => (
                <span
                  key={i}
                  className={`bems-slot ${s.mode.toLowerCase()}`}
                  style={{
                    left: `${(s.startHour / 24) * 100}%`,
                    width: `${((s.endHour - s.startHour) / 24) * 100}%`,
                  }}
                  title={`${s.startHour}–${s.endHour}시 ${SLOT_LABEL[s.mode]}`}
                >
                  {SLOT_LABEL[s.mode]}
                </span>
              ))}
          </div>
        </div>
      ))}
      <figcaption className="muted">0시 ~ 24시 · 빈 곳은 정지</figcaption>
    </figure>
  );
}

export function Schedules() {
  const { data, error, reload } = useLists<[HvacUnit[], LightingCircuit[]]>([
    "/hvac-units",
    "/lighting-circuits",
  ]);
  const [schedules, setSchedules] = useState<Record<string, Slot[]>>();
  const [tick, setTick] = useState(0);
  const [editing, setEditing] = useState<Row | null>(null);
  const [slots, setSlots] = useState<Slot[]>([]);
  const refresh = () => {
    reload();
    setTick((n) => n + 1);
  };
  const { send, pending, error: saveError, setError } = useSend(refresh);
  const guard = useDiscardGuard(
    !!editing && JSON.stringify(slots) !== JSON.stringify(editing.slots),
  );
  const [units, circuits] = data ?? [[], []];
  useEffect(() => {
    if (!data) return;
    // ponytail: 대상마다 상세를 부른다(수 대). 대상이 많아지면 스케줄 목록 API를 둔다.
    const targets: [Row["target"], { id: number }][] = [
      ...units.map((u) => ["hvac", u] as [Row["target"], { id: number }]),
      ...circuits.map((c) => ["light", c] as [Row["target"], { id: number }]),
    ];
    void Promise.all(
      targets.map(([target, row]) =>
        api<UnitDetail | CircuitDetail>(
          `${BEMS}${PATH[target]}/${row.id}/detail`,
        ).then((r) => [`${target}:${row.id}`, r.data.schedule] as const),
      ),
    )
      .then((pairs) => setSchedules(Object.fromEntries(pairs)))
      .catch(setError);
  }, [data, tick]);
  if (moduleOff(error)) return <ModuleOff />;
  const errors = fieldErrors(saveError);
  const clean = (list: Slot[]) =>
    list.map(({ dayKind, startHour, endHour, mode }) => ({
      dayKind,
      startHour,
      endHour,
      mode,
    }));
  const toRow = (
    target: Row["target"],
    targetLabel: string,
    row: HvacUnit | LightingCircuit,
  ): Row => {
    const id = `${target}:${row.id}`;
    const list = clean(schedules?.[id] ?? []);
    return {
      id,
      targetId: row.id,
      code: row.code,
      name: row.name,
      target,
      targetLabel,
      slots: list,
      weekday: summary(list, "WEEKDAY"),
      weekend: summary(list, "WEEKEND"),
      holiday: summary(list, "HOLIDAY"),
    };
  };
  const rows: Row[] = [
    ...units.map((u) => toRow("hvac", "공조기", u)),
    ...circuits.map((c) => toRow("light", "조명", c)),
  ];

  function edit(row: Row) {
    guard.guard(() => {
      setEditing(row);
      setSlots(row.slots);
      setError(undefined);
    });
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!editing) return;
    const saved = await send(
      `${PATH[editing.target]}/${editing.targetId}/schedule`,
      "PUT",
      { slots },
    );
    if (saved) setEditing(null);
  }
  const change = (i: number, patch: Partial<Slot>) =>
    setSlots(slots.map((s, j) => (j === i ? { ...s, ...patch } : s)));

  const columns: Column<Row>[] = [
    { key: "code", label: "대상" },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <button
          type="button"
          className="link-button"
          aria-pressed={editing?.id === r.id}
          onClick={() => edit(r)}
        >
          편집
        </button>
      ),
    },
    { key: "targetLabel", label: "구분" },
    { key: "name", label: "이름" },
    { key: "weekday", label: "평일" },
    { key: "weekend", label: "주말" },
    { key: "holiday", label: "휴일" },
  ];
  const modes = MODES[editing?.target ?? "hvac"];

  return (
    <div className="page-fill">
      <PageTitle
        id="B-05"
        title="운전 스케줄"
        subtitle="공조기·조명 회로의 평일·주말·휴일 운전 시간대입니다. 시간대 밖은 정지합니다"
        help="bems/b-05"
      />
      <ScreenIntro>
        휴일은 <Link to="/holidays">휴일 달력</Link>에 등록한 날입니다. 휴일
        시간대를 하나도 두지 않으면 그날은 주말 시간대를 따릅니다.
      </ScreenIntro>
      {!editing && <ErrorNotice error={saveError} />}
      <ErrorNotice error={error} retry={reload} />
      {!data || !schedules ? (
        !error && <Loading />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <DataTable
              rows={rows}
              columns={columns}
              caption="운전 스케줄"
              offset={0}
              total={rows.length}
              limit={rows.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="공조기·조명 회로가 없습니다. 구역·계측에서 등록하세요."
                  to="/bems/zones"
                  action="구역·계측으로"
                />
              }
            />
          </section>
          {editing && (
            <FormPanel
              wide
              key={editing.id}
              title={`${editing.code} 운전 스케줄`}
              guard={guard}
              onClose={() => setEditing(null)}
              onSubmit={(e) => void submit(e)}
              actions={
                <>
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    저장
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => guard.guard(() => setEditing(null))}
                  >
                    닫기
                  </button>
                  <small className="muted">
                    저장하면 다음 경계부터 적용됩니다
                  </small>
                </>
              }
            >
              <ErrorNotice
                error={Object.keys(errors).length ? undefined : saveError}
              />
              <div className="table-scroll">
                <table>
                  <caption>시간대</caption>
                  <thead>
                    <tr>
                      <th scope="col">요일</th>
                      <th scope="col">시작</th>
                      <th scope="col">종료</th>
                      <th scope="col">모드</th>
                      <th scope="col">관리</th>
                    </tr>
                  </thead>
                  <tbody>
                    {slots.map((s, i) => (
                      <tr key={i} aria-invalid={!!errors[`slots.${i}`]}>
                        <td>
                          <select
                            aria-label={`${i + 1}번째 요일`}
                            value={s.dayKind}
                            onChange={(e) =>
                              change(i, {
                                dayKind: e.target.value as DayKind,
                              })
                            }
                          >
                            {DAY_KINDS.map((d) => (
                              <option key={d} value={d}>
                                {DAY_LABEL[d]}
                              </option>
                            ))}
                          </select>
                        </td>
                        <td>
                          <select
                            aria-label={`${i + 1}번째 시작 시각`}
                            value={s.startHour}
                            onChange={(e) =>
                              change(i, { startHour: Number(e.target.value) })
                            }
                          >
                            {HOURS.slice(0, 24).map((h) => (
                              <option key={h} value={h}>
                                {h}시
                              </option>
                            ))}
                          </select>
                        </td>
                        <td>
                          <select
                            aria-label={`${i + 1}번째 종료 시각`}
                            value={s.endHour}
                            onChange={(e) =>
                              change(i, { endHour: Number(e.target.value) })
                            }
                          >
                            {HOURS.slice(1).map((h) => (
                              <option key={h} value={h}>
                                {h}시
                              </option>
                            ))}
                          </select>
                          {errors[`slots.${i}`] && (
                            <small className="field-error">
                              {errors[`slots.${i}`]}
                            </small>
                          )}
                        </td>
                        <td>
                          <select
                            aria-label={`${i + 1}번째 모드`}
                            value={s.mode}
                            disabled={modes.length === 1}
                            onChange={(e) =>
                              change(i, { mode: e.target.value as Mode | "ON" })
                            }
                          >
                            {modes.map((m) => (
                              <option key={m} value={m}>
                                {SLOT_LABEL[m]}
                              </option>
                            ))}
                          </select>
                        </td>
                        <td>
                          <button
                            type="button"
                            className="link-button"
                            onClick={() =>
                              setSlots(slots.filter((_, j) => j !== i))
                            }
                          >
                            삭제
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {!slots.length && (
                <p className="muted">
                  시간대가 없으면 {editing.targetLabel}은(는) 스케줄상
                  정지입니다.
                </p>
              )}
              <button
                type="button"
                className="secondary"
                onClick={() =>
                  setSlots([
                    ...slots,
                    {
                      dayKind: "WEEKDAY",
                      startHour: 8,
                      endHour: 19,
                      mode: modes[0],
                    },
                  ])
                }
              >
                시간대 추가
              </button>
              <Preview slots={slots} />
            </FormPanel>
          )}
        </div>
      )}
    </div>
  );
}
