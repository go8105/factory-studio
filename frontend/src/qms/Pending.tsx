// Q-03 검사 대기 — MES 완료 LOT을 읽기 전용으로 조회한다(FS-023 D9, UI-02 L 패턴).
// "검사 시작"은 LOT 값을 스냅샷으로 복사한 검사를 만들고 Q-04 입력 패널로 이동한다.
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
  ModuleOff,
  moduleOff,
  num,
  QMS,
  time,
  useSend,
  type MesLot,
} from "./common";

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
  const [includeDone, setIncludeDone] = useState(false);
  const [rows, setRows] = useState<MesLot[]>();
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

  const columns: Column<MesLot>[] = [
    { key: "lotNo", label: "LOT" },
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
        subtitle="MES에서 실적 확정이 끝난 LOT을 읽어 와 출하 전 최종검사를 시작합니다"
        help="qms/q-03"
      />
      <p className="muted" role="note">
        MES 데이터를 읽기만 합니다. 검사를 시작하면 LOT 번호·품목·양품 수량을
        검사 기록에 복사하고, 이후 MES가 바뀌어도 검사 기록은 그대로입니다.
      </p>
      <ErrorNotice error={saveError} />
      {sourceOff ? (
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
