// Q-03 검사 대기 — 출하(MES 완료 LOT)·수입(WMS 격리 입고 줄) 두 탭 (FS-023 D9, DSN-14 F11·F21).
// "검사 시작"은 원천 값을 스냅샷으로 복사한 검사를 만들고 Q-04 입력 패널로 이동한다.
// 반품·초품 탭은 ERP 반품 표가 생긴 뒤에 붙인다.
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useSession } from "../app/session";
import { api, ApiError } from "../shared/api";
import {
  Badge,
  DataTable,
  EmptyState,
  ErrorNotice,
  Loading,
  PageTitle,
  type Column,
} from "../shared/components";
import {
  LEVEL,
  LevelBadge,
  ModuleOff,
  moduleOff,
  num,
  QMS,
  time,
  useSend,
  type IncomingLot,
  type MesLot,
  SpcBadge,
} from "./common";

type Tab = "outgoing" | "incoming";
const TABS: Record<Tab, string> = { outgoing: "출하", incoming: "수입" };

const STATUS = {
  pending: ["대기", "warning"],
  drafting: ["작성 중", "warning"],
  inspected: ["검사 완료", "normal"],
} as const;
// 표본 기본값. 1차는 AQL을 계산하지 않고 작업자가 Q-04에서 고친다(모듈 설계 3장).
const DEFAULT_SAMPLE = 32;

export function Pending() {
  const { fail } = useSession();
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>("outgoing");
  const [includeDone, setIncludeDone] = useState(false);
  const [rows, setRows] = useState<MesLot[]>();
  const [incoming, setIncoming] = useState<{
    wmsEnabled: boolean;
    rows: IncomingLot[];
  }>();
  // 탭마다 원천이 다르다. 출하(MES) 오류가 수입(WMS) 탭에 새어 나오면 안 된다.
  const [incomingError, setIncomingError] = useState<unknown>();
  const [error, setError] = useState<unknown>();
  const [reload, setReload] = useState(0);
  const {
    send,
    pending,
    error: saveError,
  } = useSend(() => setReload((n) => n + 1));
  useEffect(() => {
    const controller = new AbortController();
    setError(undefined);
    setRows(undefined);
    api<MesLot[]>(`${QMS}/lookups/mes-lots?pending=${!includeDone}`, {
      signal: controller.signal,
    })
      .then((r) => {
        if (!controller.signal.aborted) setRows(r.data);
      })
      .catch((e) => {
        if (controller.signal.aborted) return;
        setError(e);
        if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
      });
    return () => controller.abort();
  }, [includeDone, reload]);

  useEffect(() => {
    if (tab !== "incoming") return;
    const controller = new AbortController();
    setIncoming(undefined);
    setIncomingError(undefined);
    api<{ wmsEnabled: boolean; rows: IncomingLot[] }>(
      `${QMS}/lookups/incoming-lots`,
      { signal: controller.signal },
    )
      .then((r) => !controller.signal.aborted && setIncoming(r.data))
      .catch((e) => {
        if (controller.signal.aborted) return;
        setIncomingError(e);
        if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
      });
    return () => controller.abort();
  }, [tab, reload]);

  if (moduleOff(error)) return <ModuleOff />;
  const sourceOff =
    error instanceof ApiError &&
    error.error.details?.reason === "SOURCE_MODULE_DISABLED";

  async function start(lot: MesLot) {
    const sample = Math.min(Number(lot.finalGoodQty), DEFAULT_SAMPLE);
    const created = await send<{ id: number }>("/inspections", "POST", {
      source: "MES",
      lotNo: lot.lotNo,
      sampleQty: String(sample),
    });
    if (created) navigate(`/qms/inspections?open=${created.id}`);
  }
  async function startIncoming(row: IncomingLot) {
    const created = await send<{ id: number }>(
      "/inspections/incoming",
      "POST",
      {
        sourceRef: row.sourceRef,
      },
    );
    if (created) navigate(`/qms/inspections?open=${created.id}`);
  }

  const incomingColumns: Column<IncomingLot & { id: number }>[] = [
    { key: "sourceRef", label: "입고 원천" },
    {
      key: "id",
      label: "관리",
      render: (r) =>
        r.hasSpec ? (
          <button
            type="button"
            className="link-button"
            disabled={pending}
            onClick={() => void startIncoming(r)}
          >
            검사 시작
          </button>
        ) : (
          <Link className="link-button" to="/qms/specs">
            수입 기준 없음 · 기준 만들기
          </Link>
        ),
    },
    {
      key: "partnerCode",
      label: "공급처",
      render: (r) => r.partnerCode ?? "—",
    },
    {
      key: "itemCode",
      label: "품목",
      render: (r) => `${r.itemCode} ${r.itemName}`,
    },
    { key: "lotNo", label: "LOT", render: (r) => r.lotNo ?? "—" },
    {
      key: "qty",
      label: "격리 수량",
      render: (r) => `${num(r.qty)} ${r.unit}`,
    },
    {
      key: "level",
      label: "검사 수준",
      render: (r) => <LevelBadge level={r.level} />,
    },
  ];

  const columns: Column<MesLot>[] = [
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
      key: "status",
      label: "관리",
      render: (r) =>
        r.draftInspectionId ? (
          <Link
            className="link-button"
            to={`/qms/inspections?open=${r.draftInspectionId}`}
          >
            이어서 입력
          </Link>
        ) : r.status === "inspected" ? (
          "—"
        ) : r.hasSpec ? (
          <button
            type="button"
            className="link-button"
            disabled={pending}
            onClick={() => void start(r)}
          >
            검사 시작
          </button>
        ) : (
          <Link className="link-button" to="/qms/specs">
            기준 없음 · 기준 만들기
          </Link>
        ),
    },
    {
      key: "itemCode",
      label: "품목",
      render: (r) => `${r.itemCode} ${r.itemName}`,
    },
    {
      key: "finalGoodQty",
      label: "최종 양품",
      render: (r) => `${num(r.finalGoodQty)} ${r.unit}`,
    },
    {
      key: "completedAt",
      label: "완료 시각",
      render: (r) => time(r.completedAt),
    },
    {
      key: "latestResult",
      label: "상태",
      render: (r) => {
        const [label, tone] = STATUS[r.status];
        return (
          <Badge tone={r.latestResult === "FAIL" ? "issue" : tone}>
            {r.latestResult === "FAIL" ? "불합격" : label}
          </Badge>
        );
      },
    },
  ];

  return (
    <div className="page-fill">
      <PageTitle
        id="Q-03"
        title="검사 대기"
        subtitle="출하는 MES 완료 LOT, 수입은 WMS 격리 입고 줄에서 검사를 시작합니다"
        help="qms/q-03"
      />
      <p className="muted" role="note">
        원천 데이터를 읽기만 합니다. 검사를 시작하면 LOT 번호·품목·수량을 검사
        기록에 복사하고, 이후 MES·WMS가 바뀌어도 검사 기록은 그대로입니다.
      </p>
      <ErrorNotice error={saveError} />
      <div className="filter-bar">
        {(Object.keys(TABS) as Tab[]).map((key) => (
          <button
            key={key}
            type="button"
            className={tab === key ? undefined : "secondary"}
            aria-pressed={tab === key}
            onClick={() => setTab(key)}
          >
            {TABS[key]}
          </button>
        ))}
      </div>
      {tab === "incoming" ? (
        <>
          <p className="muted">
            <strong>검수에서 격리된 입고 줄</strong>이 수입 검사 대상입니다.{" "}
            {LEVEL.EXEMPT} 수준으로 정한 공급처는 목록에서 빠집니다.
          </p>
          <ErrorNotice
            error={incomingError}
            retry={() => setReload((n) => n + 1)}
          />
          {!incoming ? (
            !incomingError && <Loading delay={300} />
          ) : !incoming.wmsEnabled ? (
            <EmptyState
              reason="WMS를 사용하지 않도록 설정했습니다. 수입 검사 대상을 읽을 수 없습니다."
              to="/workspace"
              action="내 공간으로"
            />
          ) : (
            <DataTable
              rows={incoming.rows.map((r, i) => ({ ...r, id: i + 1 }))}
              columns={incomingColumns}
              caption="수입 검사 대기"
              offset={0}
              total={incoming.rows.length}
              limit={incoming.rows.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="수입 검사할 입고 줄이 없습니다. WMS 검수에서 격리한 줄이 여기에 나타납니다."
                  to="/wms/receiving"
                  action="WMS 입고 검수로"
                />
              }
            />
          )}
        </>
      ) : sourceOff ? (
        <EmptyState
          reason="MES를 사용하지 않도록 설정했습니다. LOT 코드를 직접 입력해 검사할 수 있습니다."
          action="직접 입력으로 검사"
          onAction={() => navigate("/qms/inspections?manual=1")}
        />
      ) : (
        <>
          <ErrorNotice error={error} retry={() => setReload((n) => n + 1)} />
          <div className="filter-bar">
            <label className="inline-check">
              <input
                type="checkbox"
                checked={includeDone}
                onChange={(e) => setIncludeDone(e.target.checked)}
              />
              검사를 마친 LOT도 보기
            </label>
          </div>
          {!rows ? (
            !error && <Loading delay={300} />
          ) : (
            <DataTable
              rows={rows.map((r, i) => ({ ...r, id: i + 1 }))}
              columns={columns as Column<MesLot & { id: number }>[]}
              caption="검사 대기 LOT"
              offset={0}
              total={rows.length}
              limit={rows.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="검사할 LOT이 없습니다. MES에서 공정 실적을 확정하면 여기에 나타납니다."
                  to="/mes/results"
                  action="MES 실적 확정으로"
                />
              }
            />
          )}
        </>
      )}
    </div>
  );
}
