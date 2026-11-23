// E-35 월 마감·기초 잔액 (DSN-11 F57·F58).
import { useState } from "react";
import {
  Badge,
  DataTable,
  ErrorNotice,
  Loading,
  PageTitle,
} from "../shared/components";
import { Master, type InputField } from "./Master";
import { ModuleOff, moduleOff, today, useLists, useSend } from "./common";

type Period = {
  periodMonth: string;
  status: "open" | "closed";
  closedAt: string | null;
  postedCount: number;
  draftCount: number;
  unpostedCount: number;
};
const openings: InputField[] = [
  { key: "fiscalYear", label: "회계연도", maxLength: 4 },
  {
    key: "accountId",
    label: "계정",
    lookup: {
      path: "/api/v1/erp/accounts",
      code: "accountCode",
      name: "accountName",
    },
  },
  {
    key: "partnerId",
    label: "거래처",
    nullable: true,
    lookup: {
      path: "/api/v1/erp/partners",
      code: "partnerCode",
      name: "partnerName",
    },
  },
  {
    key: "side",
    label: "차·대",
    options: [
      ["DEBIT", "차변"],
      ["CREDIT", "대변"],
    ],
    initial: "DEBIT",
  },
  { key: "amount", label: "금액", initial: "0" },
];

export function Closing() {
  const [year, setYear] = useState(today().slice(0, 4));
  const { data, error, reload } = useLists<[Period[]]>([
    `/fiscal-periods?year=${year}`,
  ]);
  const { send, pending, error: saveError } = useSend(reload);
  const [done, setDone] = useState<string>();
  // 이월은 기초 잔액 목록을 밖에서 바꾼다. Master는 제 목록을 따로 불러오므로 다시 태운다.
  const [stamp, setStamp] = useState(0);
  if (moduleOff(error)) return <ModuleOff />;
  const months = data?.[0];

  async function toggle(row: Period) {
    const action = row.status === "closed" ? "reopen" : "close";
    const result = await send(
      `/fiscal-periods/${row.periodMonth}/${action}`,
      "POST",
    );
    if (result)
      setDone(
        `${row.periodMonth}을 ${action === "close" ? "마감" : "해제"}했습니다.`,
      );
  }

  async function carry() {
    const result = await send<{ fiscalYear: string; created: number }>(
      "/opening-balances/carry-forward",
      "POST",
      { fiscalYear: year },
    );
    if (result) {
      setStamp((n) => n + 1);
      setDone(
        `${result.fiscalYear}년 기초 잔액 ${result.created}건을 만들었습니다.`,
      );
    }
  }

  return (
    <div className="page-fill">
      <PageTitle
        id="E-35"
        title="월 마감·기초 잔액"
        help="erp/e-35"
        actions={
          <span className="row-actions">
            <label>
              회계연도
              <input
                type="number"
                min={2000}
                max={2999}
                value={year}
                onChange={(e) => setYear(e.target.value)}
              />
            </label>
            <button
              type="button"
              disabled={pending}
              onClick={() => void carry()}
            >
              {Number(year) + 1}년으로 이월
            </button>
          </span>
        }
      />
      <p className="notice">
        마감한 달에는 전표를 넣지도 확정하지도 역분개하지도 못합니다. 업무는
        막지 않습니다 — 확정은 되고 전표만 E-31에 남습니다. 작성 중인 전표가
        있으면 마감할 수 없고, 해제는 다음 달이 열려 있을 때만 됩니다.
      </p>
      <ErrorNotice error={error} retry={reload} />
      <ErrorNotice error={saveError} />
      {done && <p role="status">{done}</p>}
      {!months ? (
        <Loading />
      ) : (
        <DataTable
          rows={months.map((m) => ({ ...m, id: m.periodMonth }))}
          columns={[
            { key: "periodMonth", label: "회계 월" },
            {
              key: "status",
              label: "상태",
              render: (r) =>
                r.status === "closed" ? (
                  <Badge tone="warning">마감</Badge>
                ) : (
                  <Badge>열림</Badge>
                ),
            },
            { key: "postedCount", label: "전표" },
            {
              key: "draftCount",
              label: "작성 중",
              render: (r) => (r.draftCount ? String(r.draftCount) : "—"),
            },
            {
              key: "unpostedCount",
              label: "미반영 업무",
              render: (r) =>
                r.unpostedCount ? (
                  <Badge tone="warning">{r.unpostedCount}건</Badge>
                ) : (
                  "—"
                ),
            },
            {
              key: "closedAt",
              label: "관리",
              render: (r) => (
                <button
                  type="button"
                  className="link-button"
                  disabled={pending}
                  onClick={() => void toggle(r)}
                >
                  {r.status === "closed" ? "해제" : "마감"}
                </button>
              ),
            },
          ]}
          caption={`${year}년 회계 기간`}
          offset={0}
          total={months.length}
          limit={months.length}
          onPage={() => undefined}
        />
      )}
      <p className="muted" role="note">
        기초 잔액은 연도·계정(·거래처)당 한 건이고, 그 해 1월이 열려 있을 때만
        고칠 수 있습니다. 이월은 전년 12월을 마감한 뒤에 합니다 — 재무상태표
        계정은 그대로, 손익 계정은 모아서 이월이익잉여금으로 옮깁니다.
      </p>
      <Master
        key={stamp}
        embedded
        id="E-35"
        title="기초 잔액"
        path="/api/v1/erp/opening-balances"
        fields={openings}
      />
    </div>
  );
}
