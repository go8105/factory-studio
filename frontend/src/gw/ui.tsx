import { Link } from "react-router-dom";
import {
  Badge,
  DataTable,
  EmptyState,
  ErrorNotice,
  type DiscardGuard,
} from "../shared/components";
import { labels, time, useRole, type Event, type Snapshot } from "./common";
export function RoleBar({
  guard,
  pending = false,
}: {
  guard?: DiscardGuard;
  pending?: boolean;
}) {
  const role = useRole();
  return (
    <div className="gw-role">
      <ErrorNotice error={role.error} />
      {role.busy && <p role="status">요청을 처리하고 있습니다.</p>}
      <label>
        담당자 역할 체험{" "}
        <select
          aria-label="담당자 역할 체험"
          value={role.person}
          disabled={pending || role.busy}
          onChange={(e) => {
            const id = e.target.value;
            const change = () => role.setPerson(id);
            if (guard) guard.guard(change);
            else change();
          }}
        >
          <option value="">담당자 선택</option>
          {role.people
            .filter((p) => p.isActive)
            .map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} · {labels[p.jobRole]}
              </option>
            ))}
        </select>
      </label>
      <p className="muted">
        내 공간의 합성 담당자로 업무를 체험합니다. 실제 직원 로그인 변경이
        아닙니다.
      </p>
      {!role.error && !role.people.length && (
        <Link to="/gw/people">체험 담당자 먼저 등록</Link>
      )}
    </div>
  );
}
export function Status({ value }: { value: string }) {
  return (
    <Badge
      tone={
        ["REJECTED", "WITHDRAWN"].includes(value)
          ? "issue"
          : ["DRAFT", "WAITING", "IN_REVIEW"].includes(value)
            ? "warning"
            : "normal"
      }
    >
      {labels[value] ?? value}
    </Badge>
  );
}
export function Events({ rows }: { rows: Event[] }) {
  return (
    <DataTable
      rows={rows}
      columns={[
        { key: "eventSeq", label: "순서" },
        {
          key: "eventType",
          label: "행위",
          render: (r) =>
            r.details?.participantRole === "REFERENCE" &&
            r.eventType === "CONSENTED"
              ? "참고 의견"
              : (labels[r.eventType] ?? r.eventType),
        },
        {
          key: "personName",
          label: "합성 담당자",
          render: (r) =>
            r.onBehalfOfPersonId
              ? `${r.personName} (위임 · 원 담당자 ${r.details?.originalPersonName ?? r.onBehalfOfPersonId})`
              : r.personName,
        },
        {
          key: "actorKind",
          label: "실제 주체",
          render: (r) =>
            r.actorKind === "SEED"
              ? "합성 이력"
              : r.actorKind === "GUEST"
                ? "게스트"
                : "회원",
        },
        {
          key: "reason",
          label: "사유",
          render: (r) =>
            r.reason ??
            (r.eventType === "SKIPPED"
              ? `${r.details?.personName ?? "참여자"} · ${r.details?.cause === "SUBMITTED" ? "상신 시 전결" : r.details?.cause === "APPROVED" || r.details?.cause === "CONSENTED" ? "필수 처리 완료 후 참고 생략" : (labels[r.details?.cause ?? ""] ?? "진행 종료")}`
              : "—"),
        },
        {
          key: "createdAt",
          label: "처리 시각",
          render: (r) => time(r.createdAt),
        },
      ]}
      caption="사건 이력"
      offset={0}
      total={rows.length}
      limit={rows.length || 1}
      onPage={() => {}}
    />
  );
}
export function SnapshotView({ value }: { value: Snapshot }) {
  return (
    <section>
      <h3>고정된 원문 · {value.documentNo}</h3>
      <p>
        {value.partnerName} · 공급가 {value.supplyAmount} / 세액{" "}
        {value.taxAmount} / 합계 {value.totalAmount} {value.currency}
      </p>
      <DataTable
        rows={(value.lines ?? []).map((r) => ({ ...r, id: r.lineNo }))}
        columns={[
          { key: "lineNo", label: "행" },
          { key: "itemCode", label: "품목" },
          { key: "quantity", label: "수량" },
          { key: "unit", label: "단위" },
          { key: "unitPrice", label: "단가" },
          { key: "totalAmount", label: "합계" },
        ]}
        caption="원문 명세"
        offset={0}
        total={(value.lines ?? []).length}
        limit={(value.lines ?? []).length || 1}
        onPage={() => {}}
      />
    </section>
  );
}
export function NoRole() {
  const role = useRole();
  if (role.error)
    return (
      <EmptyState
        reason="담당자 조회를 완료하지 못했습니다. GW 사용 설정을 확인하거나 다시 시도하세요."
        to="/workspace"
        action="내 공간 설정"
      />
    );
  return (
    <EmptyState
      reason="체험 담당자를 선택하세요. 담당자가 없다면 먼저 등록할 수 있습니다."
      to="/gw/people"
      action="체험 담당자 등록"
    />
  );
}
