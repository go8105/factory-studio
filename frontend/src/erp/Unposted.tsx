// E-31 회계 미반영 현황 (DSN-11 F44)
import { useState } from "react";
import {
  Badge,
  DataTable,
  ErrorNotice,
  Loading,
  PageTitle,
} from "../shared/components";
import { ModuleOff, moduleOff, useLists, useSend, won } from "./common";

type Row = {
  sourceKind: string;
  entryKind: string;
  sourceId: number;
  label: string;
  ref: string;
  entryDate: string;
  amount: string;
  reason: string | null;
  reasonText: string;
  postable: boolean;
};

export function Unposted() {
  const { data, error, reload } = useLists<[Row[]]>(["/unposted"]);
  const { send, pending, error: saveError } = useSend(reload);
  const [done, setDone] = useState<string>();
  const rows = data?.[0];
  if (moduleOff(error)) return <ModuleOff />;
  const ready = (rows ?? []).filter((r) => r.postable);

  async function postAll() {
    const result = await send<{ posted: number; skipped: number }>(
      "/unposted/post",
      "POST",
      {
        targets: ready.map((r) => ({
          sourceKind: r.sourceKind,
          entryKind: r.entryKind,
          sourceId: r.sourceId,
        })),
      },
    );
    if (result) setDone(`${result.posted}건 반영, ${result.skipped}건 건너뜀.`);
  }

  return (
    <div className="page-fill">
      <PageTitle
        id="E-31"
        title="회계 미반영 현황"
        help="erp/e-31"
        actions={
          <button
            type="button"
            disabled={pending || !ready.length}
            onClick={() => void postAll()}
          >
            반영 가능한 {ready.length}건 반영
          </button>
        }
      />
      <p className="muted" role="note">
        확정했는데 전표가 없는 업무입니다. 업무는 회계 때문에 막히지 않습니다 —
        규칙이 없거나 그 달이 마감됐으면 업무만 확정되고 여기 남습니다. 사유를
        없앤 뒤 한꺼번에 반영하세요.
      </p>
      <ErrorNotice error={error} retry={reload} />
      <ErrorNotice error={saveError} />
      {done && <p role="status">{done}</p>}
      {!rows ? (
        <Loading />
      ) : (
        <DataTable
          rows={rows.map((r, id) => ({ ...r, id }))}
          columns={[
            { key: "entryDate", label: "일자" },
            { key: "label", label: "업무" },
            { key: "ref", label: "문서" },
            { key: "amount", label: "금액", render: (r) => won(r.amount) },
            {
              key: "reason",
              label: "왜 없나",
              wrap: true,
              render: (r) =>
                r.postable ? (
                  <Badge>지금 반영 가능</Badge>
                ) : (
                  <Badge tone="warning">{r.reasonText}</Badge>
                ),
            },
          ]}
          caption="회계 미반영"
          offset={0}
          total={rows.length}
          limit={rows.length || 1}
          onPage={() => undefined}
          empty="미반영 업무가 없습니다. 모두 전표로 반영됐습니다."
        />
      )}
    </div>
  );
}
