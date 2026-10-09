import { useState, type FormEvent } from "react";
import {
  DataTable,
  EmptyState,
  ErrorNotice,
  Field,
  FormPanel,
  Loading,
  PageTitle,
  useDiscardGuard,
} from "../shared/components";
import {
  documentKinds,
  labels,
  time,
  useGet,
  useRole,
  useSend,
  type Page,
} from "./common";
import { RoleBar } from "./ui";
type Grant = {
  id: string;
  delegatorPersonId: string;
  delegatePersonId: string;
  delegatorName: string;
  delegateName: string;
  startsAt: string;
  endsAt: string;
  documentKind: string | null;
  maxAmount: string | null;
  reason: string;
  revokedAt: string | null;
  version: number;
};
export function Delegations() {
  const revokeGuard = useDiscardGuard(false);
  const role = useRole();
  const [offset, setOffset] = useState(0);
  const [create, setCreate] = useState(false);
  const [revoke, setRevoke] = useState<Grant>();
  const list = useGet<Page<Grant>>(`/delegations?offset=${offset}&limit=20`);
  const request = useSend();
  async function cancel(g: Grant) {
    const saved = await request.send<Grant>(
      `/delegations/${g.id}/revoke`,
      "POST",
      { actingPersonId: role.person, expectedVersion: g.version },
    );
    if (saved) {
      setRevoke(undefined);
      list.reload();
    }
  }
  return (
    <div className="page-fill">
      <PageTitle
        id="G-09"
        title="결재 위임"
        help="gw/g-09"
        actions={
          <button
            disabled={!role.person || role.busy}
            onClick={() => setCreate(true)}
          >
            위임 등록
          </button>
        }
      />
      <RoleBar />
      <p>
        선택한 담당자가 자신의 결재 권한을 기간·종류·한도 내에서 위임합니다.
        연쇄 위임과 겹치는 기간은 허용하지 않습니다. 기안자나 문서의 다른
        참여자는 대리 처리할 수 없습니다. 종료 시각은 포함하지 않습니다.
      </p>
      <ErrorNotice error={request.error} />
      <ErrorNotice error={list.error} />
      {list.data ? (
        <DataTable
          rows={list.data.rows}
          caption="결재 위임"
          offset={offset}
          limit={20}
          total={list.data.total}
          onPage={setOffset}
          columns={[
            { key: "delegatorName", label: "원 담당자" },
            { key: "delegateName", label: "위임받은 담당자" },
            { key: "startsAt", label: "시작", render: (r) => time(r.startsAt) },
            { key: "endsAt", label: "종료", render: (r) => time(r.endsAt) },
            {
              key: "documentKind",
              label: "종류",
              render: (r) => (r.documentKind ? labels[r.documentKind] : "전체"),
            },
            {
              key: "maxAmount",
              label: "한도 (KRW)",
              render: (r) => r.maxAmount ?? "제한 없음",
            },
            { key: "reason", label: "사유" },
            {
              key: "revokedAt",
              label: "상태",
              render: (r) =>
                r.revokedAt
                  ? "해제"
                  : new Date(r.endsAt).getTime() <= Date.now()
                    ? "종료"
                    : new Date(r.startsAt).getTime() > Date.now()
                      ? "예정"
                      : "유효",
            },
            {
              key: "id",
              label: "관리",
              render: (r) =>
                !r.revokedAt && r.delegatorPersonId === role.person ? (
                  <button
                    disabled={request.pending}
                    onClick={() => setRevoke(r)}
                  >
                    위임 해제
                  </button>
                ) : (
                  "—"
                ),
            },
          ]}
          empty={
            <EmptyState
              reason="등록된 위임이 없습니다."
              action="위임 등록"
              onAction={() => setCreate(true)}
            />
          }
        />
      ) : (
        !list.error && <Loading />
      )}
      {revoke && (
        <FormPanel
          guard={revokeGuard}
          title="위임 해제 확인"
          onClose={() => setRevoke(undefined)}
          onSubmit={(e) => {
            e.preventDefault();
            void cancel(revoke);
          }}
          actions={<button disabled={request.pending}>해제 확정</button>}
        >
          <p>
            {revoke.delegatorName} → {revoke.delegateName} 위임을 해제합니다.
            이미 처리한 결재 이력은 보존됩니다.
          </p>
        </FormPanel>
      )}
      {create && (
        <GrantEditor
          close={() => setCreate(false)}
          done={() => {
            setCreate(false);
            list.reload();
          }}
        />
      )}
    </div>
  );
}
function GrantEditor({ close, done }: { close: () => void; done: () => void }) {
  const role = useRole();
  const request = useSend();
  const guard = useDiscardGuard(true);
  const [delegate, setDelegate] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [kind, setKind] = useState("");
  const [max, setMax] = useState("");
  const [reason, setReason] = useState("");
  async function submit(e: FormEvent) {
    e.preventDefault();
    const saved = await request.send<Grant>("/delegations", "POST", {
      actingPersonId: role.person,
      delegatePersonId: delegate,
      startsAt: new Date(start).toISOString(),
      endsAt: new Date(end).toISOString(),
      documentKind: kind || null,
      maxAmount: max || null,
      reason,
    });
    if (saved) done();
  }
  return (
    <FormPanel
      title="위임 등록"
      guard={guard}
      onClose={close}
      onSubmit={(e) => void submit(e)}
      actions={<button disabled={request.pending || !role.person}>등록</button>}
    >
      <RoleBar guard={guard} pending={request.pending} />
      <ErrorNotice error={request.error} />
      <fieldset disabled={request.pending}>
        <label>
          위임받을 담당자
          <select
            required
            aria-label="위임받을 담당자"
            value={delegate}
            onChange={(e) => setDelegate(e.target.value)}
          >
            <option value="">선택</option>
            {role.people
              .filter((p) => p.isActive && p.id !== role.person)
              .map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
          </select>
        </label>
        <Field
          label="시작 시각 (현재 지역 시간)"
          type="datetime-local"
          required
          value={start}
          onChange={(e) => setStart(e.target.value)}
        />
        <Field
          label="종료 시각 (미포함)"
          type="datetime-local"
          required
          min={start}
          value={end}
          onChange={(e) => setEnd(e.target.value)}
        />
        <label>
          문서 종류
          <select
            aria-label="위임 문서 종류"
            value={kind}
            onChange={(e) => setKind(e.target.value)}
          >
            <option value="">전체 종류</option>
            {documentKinds.map((k) => (
              <option key={k} value={k}>
                {labels[k]}
              </option>
            ))}
          </select>
        </label>
        <Field
          label="금액 한도 (KRW, 비우면 제한 없음)"
          value={max}
          onChange={(e) => setMax(e.target.value)}
        />
        <Field
          label="위임 사유"
          required
          minLength={2}
          maxLength={500}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
      </fieldset>
    </FormPanel>
  );
}
