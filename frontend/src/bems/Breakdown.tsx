// B-02 에너지 분해 — 사업장(FEMS) − 제조(FEMS) − 공용(BEMS) = 잔여 (UI-02 L 패턴, F-02 기준).
// FEMS 교차 조회 시연 화면: FEMS 값은 fs/fems/interface.py로 읽기만 한다(FS-025 D20).
import { useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../shared/api";
import {
  Badge,
  DataTable,
  EmptyState,
  ErrorNotice,
  Loading,
  PageTitle,
  type Column,
} from "../shared/components";
import { ModuleOff, moduleOff, num, useGet, type BreakdownRow } from "./common";

type Data = {
  granularity: "day" | "month";
  from: string;
  to: string;
  rows: BreakdownRow[];
};
type Row = BreakdownRow & {
  id: number;
  lighting?: string;
  hvac?: string;
  office?: string;
};
type Filter = { granularity: "day" | "month"; from: string; to: string };

const sum = (
  rows: BreakdownRow[],
  key: "site" | "manufacturing" | "common" | "residual",
) => String(rows.reduce((t, r) => t + Number(r[key]), 0));

/** 기간 합계 비율 한 줄(색과 글자 함께). 잔여가 음수면 막대에서 빼고 글자로만 적는다. */
function Shares({
  caption,
  site,
  parts,
}: {
  caption: string;
  site: string;
  parts: [string, string][];
}) {
  const pct = (v: string) =>
    Number(site) ? (Number(v) / Number(site)) * 100 : 0;
  return (
    <figure className="bems-shares" aria-label={caption}>
      <figcaption>
        {caption} · 사업장 {num(site, 0)} kWh
      </figcaption>
      <div className="bems-shares-bar" aria-hidden="true">
        {parts.map(([label, v]) => (
          <span
            key={label}
            className={`share-${label}`}
            style={{ width: `${Math.max(0, pct(v))}%` }}
          />
        ))}
      </div>
      <p>
        {parts
          .map(([label, v]) => `${label} ${num(v, 0)} kWh (${num(pct(v))}%)`)
          .join(" · ")}
      </p>
    </figure>
  );
}

export function Breakdown() {
  const [draft, setDraft] = useState<Filter>({
    granularity: "day",
    from: "",
    to: "",
  });
  const [applied, setApplied] = useState(draft);
  const query = new URLSearchParams(
    Object.entries(applied).filter(([, v]) => v) as [string, string][],
  ).toString();
  const { data, error, reload } = useGet<Data>(`/breakdown?${query}`);
  if (moduleOff(error)) return <ModuleOff />;
  const femsOff =
    error instanceof ApiError &&
    error.error.details?.reason === "SOURCE_MODULE_DISABLED";
  const rows: Row[] = (data?.rows ?? []).map((r, id) => ({
    ...r,
    id,
    lighting: r.commonByUsage.LIGHTING,
    hvac: r.commonByUsage.HVAC,
    office: r.commonByUsage.OFFICE,
  }));
  const mismatches = rows.filter((r) => r.mismatch).length;
  const kwh = (k: keyof Row) => (r: Row) => num(r[k] as string, 0);
  const columns: Column<Row>[] = [
    { key: "period", label: "기간" },
    { key: "site", label: "사업장 전체", render: kwh("site") },
    { key: "manufacturing", label: "제조(FEMS)", render: kwh("manufacturing") },
    { key: "common", label: "공용 합", render: kwh("common") },
    { key: "lighting", label: "조명", render: kwh("lighting") },
    { key: "hvac", label: "공조", render: kwh("hvac") },
    { key: "office", label: "사무동", render: kwh("office") },
    { key: "residual", label: "잔여", render: kwh("residual") },
    {
      key: "mismatch",
      label: "상태",
      render: (r) => (
        <>
          {r.mismatch ? (
            <Badge tone="issue">불일치</Badge>
          ) : (
            <Badge>정상</Badge>
          )}
          {r.missingHours > 0 && (
            <small className="muted"> 계측 누락 {r.missingHours}시간</small>
          )}
        </>
      ),
    },
  ];

  return (
    <div className="page-fill">
      <PageTitle
        id="B-02"
        title="에너지 분해"
        subtitle="사업장 전력을 제조·공용·잔여로 나눕니다"
        help="bems/b-02"
      />
      <p className="muted" role="note">
        사업장 전력과 제조 전력은 FEMS에서 읽어 옵니다. BEMS는 FEMS 데이터를
        바꾸지 않습니다.
      </p>
      <form
        className="filter-bar"
        onSubmit={(e) => {
          e.preventDefault();
          setApplied(draft);
        }}
      >
        <label>
          단위
          <select
            value={draft.granularity}
            onChange={(e) =>
              setDraft({
                ...draft,
                granularity: e.target.value as Filter["granularity"],
              })
            }
          >
            <option value="day">일</option>
            <option value="month">월</option>
          </select>
        </label>
        <label>
          시작일
          <input
            type="date"
            value={draft.from}
            onChange={(e) => setDraft({ ...draft, from: e.target.value })}
          />
        </label>
        <label>
          종료일
          <input
            type="date"
            value={draft.to}
            onChange={(e) => setDraft({ ...draft, to: e.target.value })}
          />
        </label>
        <button type="submit">조회</button>
      </form>
      {femsOff ? (
        <EmptyState
          reason="FEMS를 사용하지 않도록 설정했습니다. 공용 계측(B-03)과 공조 운전은 그대로 쓸 수 있습니다."
          to="/workspace"
          action="내 공간에서 FEMS 켜기"
        />
      ) : (
        <>
          <ErrorNotice error={error} retry={reload} />
          {!data ? (
            !error && <Loading delay={300} />
          ) : (
            <>
              {rows.length > 0 && (
                <Shares
                  caption={`기간 합계 ${data.from} ~ ${data.to}`}
                  site={sum(rows, "site")}
                  parts={[
                    ["제조", sum(rows, "manufacturing")],
                    ["공용", sum(rows, "common")],
                    ["잔여", sum(rows, "residual")],
                  ]}
                />
              )}
              {mismatches > 0 && (
                <p className="notice" role="note">
                  불일치 {mismatches}건: 공용 계측이 수전보다 크거나 설비 배분이
                  빠졌을 수 있습니다.{" "}
                  <Link to="/fems/allocations">
                    FEMS F-03 설비별 배분 확인 →
                  </Link>
                </p>
              )}
              <DataTable
                rows={rows}
                columns={columns}
                caption="에너지 분해"
                offset={0}
                total={rows.length}
                limit={rows.length || 1}
                onPage={() => undefined}
                empty={
                  <EmptyState
                    reason="이 기간의 전력 기록이 없습니다."
                    to="/bems/zones"
                    action="구역·계측으로"
                  />
                }
              />
            </>
          )}
        </>
      )}
    </div>
  );
}
