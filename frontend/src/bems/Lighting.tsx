// B-08 조명 제어 — 조명 회로 목록 → 상세(상태·켜기/끄기·최근 명령) (UI-03 V 패턴, B-04와 같은 틀).
// 조명은 켜기·끄기만 한다(DSN-16 Q3). 스케줄은 B-05에서 함께 고친다.
import { useEffect, useState } from "react";
import { api } from "../shared/api";
import {
  Badge,
  DataTable,
  DetailPanel,
  EmptyState,
  ErrorNotice,
  Loading,
  PageTitle,
  RevealAnchor,
  type Column,
} from "../shared/components";
import {
  AdvanceControl,
  BEMS,
  commandText,
  LIGHT_LABEL,
  ModuleOff,
  moduleOff,
  nextBoundary,
  num,
  REJECT_LABEL,
  SOURCE_LABEL,
  time,
  useGet,
  useLists,
  useSend,
  type CircuitDetail,
  type Clock,
  type Command,
  type LightingCircuit,
  type Zone,
} from "./common";

export function Lighting() {
  const { data, error, reload } = useLists<[LightingCircuit[], Zone[]]>([
    "/lighting-circuits",
    "/zones",
  ]);
  const clock = useGet<Clock>("/simulation/clock");
  const [openId, setOpenId] = useState<number | null>(null);
  const [detail, setDetail] = useState<CircuitDetail>();
  const [tick, setTick] = useState(0);
  const [message, setMessage] = useState("");
  const refresh = () => {
    reload();
    clock.reload();
    setTick((n) => n + 1);
  };
  const { send, pending, error: saveError, setError } = useSend(refresh);
  useEffect(() => {
    if (!openId) return;
    void api<CircuitDetail>(`${BEMS}/lighting-circuits/${openId}/detail`)
      .then((r) => setDetail(r.data))
      .catch(setError);
  }, [openId, tick]);
  if (moduleOff(error)) return <ModuleOff />;
  const [circuits, zones] = data ?? [[], []];
  const zoneName = (id: number) => zones.find((z) => z.id === id)?.name ?? "—";
  const circuit = detail?.id === openId ? detail : undefined;

  async function command(on: boolean) {
    if (!circuit) return;
    setMessage("");
    const r = await send<Command>("/commands", "POST", {
      zoneId: circuit.zoneId,
      lightingCircuitId: circuit.id,
      command: on ? "POWER_ON" : "POWER_OFF",
    });
    if (!r) return;
    if (r.result === "REJECTED")
      setMessage(
        `거부됨: ${commandText(r)} — ${REJECT_LABEL[r.rejectReason ?? ""] ?? r.rejectReason}. 이력에 남겼습니다.`,
      );
    else {
      const boundary =
        clock.data && circuit.schedule.length
          ? nextBoundary(circuit.schedule, clock.data.next)
          : null;
      setMessage(
        `적용: ${commandText(r)}. ` +
          (boundary
            ? `다음 스케줄 경계(${time(boundary)})까지 수동 운전, 이후 스케줄로 돌아갑니다.`
            : "스케줄이 없어 다음 명령 전까지 수동 운전을 유지합니다."),
      );
    }
  }

  const columns: Column<LightingCircuit>[] = [
    { key: "code", label: "회로" },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <button
          type="button"
          className="link-button"
          aria-pressed={openId === r.id}
          onClick={() => {
            setOpenId(r.id);
            setMessage("");
            setError(undefined);
          }}
        >
          상세
        </button>
      ),
    },
    { key: "name", label: "이름" },
    { key: "zoneId", label: "구역", render: (r) => zoneName(r.zoneId) },
    {
      key: "state",
      label: "상태",
      render: (r) =>
        r.isActive ? (
          LIGHT_LABEL[r.state]
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
    { key: "ratedKw", label: "정격 kW", render: (r) => num(r.ratedKw, 2) },
    {
      key: "stateChangedAt",
      label: "상태 변경",
      render: (r) => (r.stateChangedAt ? time(r.stateChangedAt) : "—"),
    },
  ];

  return (
    <div className="page-fill">
      <PageTitle
        id="B-08"
        title="조명 제어"
        subtitle="구역별 조명 회로를 켜고 끕니다. 운전 시간대는 운전 스케줄에서 정합니다"
        help="bems/b-08"
        actions={<AdvanceControl choices={[1, 3, 6]} onDone={refresh} />}
      />
      <ErrorNotice error={error} retry={reload} />
      {!data ? (
        !error && <Loading />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <DataTable
              rows={circuits}
              columns={columns}
              caption="조명 회로 목록"
              offset={0}
              total={circuits.length}
              limit={circuits.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="조명 회로가 없습니다. 구역·계측에서 조명 회로를 등록하세요."
                  to="/bems/zones"
                  action="구역·계측으로"
                />
              }
            />
          </section>
          <RevealAnchor when={openId} />
          {openId && (
            <DetailPanel
              wide
              title={circuit ? `${circuit.code} ${circuit.name}` : "조명 회로"}
              onClose={() => setOpenId(null)}
            >
              {!circuit ? (
                <Loading />
              ) : (
                <>
                  <p>
                    상태 <strong>{LIGHT_LABEL[circuit.state]}</strong> ·{" "}
                    {SOURCE_LABEL[circuit.controlSource]} 운전 · 정격{" "}
                    {num(circuit.ratedKw, 2)} kW · {zoneName(circuit.zoneId)}
                  </p>
                  <div className="row-actions">
                    <button
                      type="button"
                      className="secondary"
                      disabled={pending}
                      onClick={() => void command(circuit.state === "OFF")}
                    >
                      {circuit.state === "OFF" ? "켜기" : "끄기"}
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
                        {circuit.commands.map((c) => (
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
                  {!circuit.commands.length && (
                    <p className="muted">명령 이력이 없습니다.</p>
                  )}
                </>
              )}
            </DetailPanel>
          )}
        </div>
      )}
    </div>
  );
}
