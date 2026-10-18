import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ErrorNotice,
  Field,
  FormPanel,
  Loading,
  useDiscardGuard,
} from "../shared/components";
import { useGet, useRole, useSend } from "./common";
type Review = {
  id: string;
  kind: "documents" | "posts";
  sourceId: string;
  dueOn: string;
  state: string;
  version: number;
  reason: string;
  revisionNo: number;
  currentPolicy: boolean;
  canReadSource: boolean;
  effectiveHold: boolean;
};
type History = {
  total: number;
  items: Review[];
  companyHold: boolean;
  holdReason: string | null;
  settingsVersion: number;
};
type Command = {
  title: string;
  path: string;
  body: Record<string, unknown>;
  notice: string;
};
const labels: Record<string, string> = {
  DUE: "검토 대기",
  HELD: "개별 보류",
  ARCHIVE_PREPARED: "보관 준비",
  ARCHIVED: "보관 완료",
};
export function RetentionReviews({
  canEdit,
  disabled,
  onEditingChange,
  onSettingsVersionChange,
}: {
  canEdit: boolean;
  disabled: boolean;
  onEditingChange?: (editing: boolean) => void;
  onSettingsVersionChange?: (version: number) => void;
}) {
  const role = useRole();
  const [offset, setOffset] = useState(0);
  const [state, setState] = useState("");
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [command, setCommand] = useState<Command>();
  const [message, setMessage] = useState("");
  const [eventRefresh, setEventRefresh] = useState(0);
  const history = useGet<History>(
    `/retention-reviews?offset=${offset}&limit=20${state ? `&state=${state}` : ""}${query ? `&sourceId=${query}` : ""}`,
  );
  useEffect(() => {
    onEditingChange?.(Boolean(command));
    return () => onEditingChange?.(false);
  }, [command, onEditingChange]);
  const unavailable = disabled || Boolean(command);
  if (history.error)
    return <ErrorNotice error={history.error} retry={history.reload} />;
  if (!history.data) return <Loading />;
  const data = history.data;
  function open(
    title: string,
    path: string,
    body: Record<string, unknown>,
    notice: string,
  ) {
    setMessage("");
    setCommand({ title, path, body, notice });
  }
  return (
    <section aria-label="보관 검토">
      <h2>보관 검토 · 보존 중지</h2>
      <p>
        기한이 지난 일반 기안·게시글의 검토 기록입니다. 원본은 삭제하지
        않습니다. 원문 권한이 없는 자료는 식별자·기한·상태만 표시합니다.
      </p>
      <p role="status">
        회사 전체 보존 중지:{" "}
        {data.companyHold
          ? "적용 중 · 해제할 때까지 보관 준비 차단"
          : "해제 상태"}
      </p>
      {data.holdReason && (
        <p>최근 회사 보존 중지 변경 사유: {data.holdReason}</p>
      )}
      {canEdit && (
        <>
          <button
            disabled={unavailable || !data.settingsVersion}
            onClick={() =>
              open(
                "검토 대상 갱신",
                "/retention-reviews/refresh",
                { expectedVersion: data.settingsVersion },
                "현재 운영 기준으로 기한이 지난 대상을 최대 200건씩 추가합니다. 기존 검토 상태와 원본은 바꾸지 않습니다.",
              )
            }
          >
            검토 대상 갱신
          </button>
          <button
            disabled={unavailable || !data.settingsVersion}
            onClick={() =>
              open(
                data.companyHold
                  ? "회사 보존 중지 해제"
                  : "회사 전체 보존 중지",
                "/retention-company-hold",
                {
                  expectedVersion: data.settingsVersion,
                  hold: !data.companyHold,
                },
                data.companyHold
                  ? "회사 중지를 해제해도 개별 보류는 유지됩니다. 해제 사유와 시각을 이력에 남깁니다."
                  : "모든 보관 준비를 해제할 때까지 중지합니다. 원문 열람과 검토 대상 갱신은 유지합니다.",
              )
            }
          >
            {data.companyHold ? "회사 보존 중지 해제" : "회사 전체 보존 중지"}
          </button>
        </>
      )}
      {!data.settingsVersion && <p>운영 기준을 먼저 적용하세요.</p>}
      <label>
        검토 상태
        <select
          value={state}
          disabled={unavailable}
          onChange={(e) => {
            setState(e.target.value);
            setOffset(0);
          }}
        >
          <option value="">전체 상태</option>
          {Object.entries(labels).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          setQuery(search);
          setOffset(0);
        }}
      >
        <Field
          label="원문 식별자 검색"
          value={search}
          pattern="[1-9][0-9]{0,18}"
          maxLength={19}
          disabled={unavailable}
          onChange={(e) => setSearch(e.target.value)}
        />
        <button disabled={unavailable}>식별자로 검색</button>
      </form>
      <p>총 {data.total}건 · 검토 기한 순</p>
      {data.total === 0 && (
        <p>
          조건에 맞는 검토 기록이 없습니다. 기준을 적용한 뒤 검토 대상을
          갱신하세요.
        </p>
      )}
      <ul>
        {data.items.map((item) => (
          <li key={item.id}>
            <p>
              {item.kind === "documents" ? "일반 기안" : "게시글"} #
              {item.sourceId} · {labels[item.state]} · 검토 기한 {item.dueOn}
            </p>
            <p>
              기준 {item.revisionNo}차 (
              {item.currentPolicy ? "현재 기준" : "이전 기준"})
              {item.effectiveHold ? " · 보류 적용 중" : ""}
            </p>
            <p>검토 사유: {item.reason}</p>
            {item.canReadSource ? (
              <Link
                to={`/gw/${item.kind === "documents" ? "documents" : "board"}?companyId=${role.companyId}&open=${item.sourceId}`}
              >
                원문 열기
              </Link>
            ) : (
              <p>원문 열람 권한 없음</p>
            )}
            {canEdit && item.state !== "ARCHIVED" && (
              <>
                <button
                  disabled={unavailable}
                  onClick={() =>
                    open(
                      item.state === "HELD" ? "개별 보류 해제" : "개별 보류",
                      `/retention-reviews/${item.id}/transition`,
                      {
                        expectedVersion: item.version,
                        state: item.state === "HELD" ? "DUE" : "HELD",
                      },
                      "이전 기준에 남아 있는 보류도 같은 원문의 보관 준비를 차단합니다. 원본 내용은 변경하지 않습니다.",
                    )
                  }
                >
                  {item.state === "HELD" ? "개별 보류 해제" : "개별 보류"}
                </button>
                {item.state === "DUE" &&
                  item.currentPolicy &&
                  item.canReadSource &&
                  !item.effectiveHold && (
                    <button
                      disabled={unavailable}
                      onClick={() =>
                        open(
                          "보관 준비",
                          `/retention-reviews/${item.id}/transition`,
                          {
                            expectedVersion: item.version,
                            state: "ARCHIVE_PREPARED",
                          },
                          "원문을 검토한 뒤 준비 상태만 기록합니다. 보관본 생성·검증·원본 삭제 또는 보관 완료가 아닙니다.",
                        )
                      }
                    >
                      보관 준비
                    </button>
                  )}
                {item.state === "ARCHIVE_PREPARED" && (
                  <button
                    disabled={unavailable}
                    onClick={() =>
                      open(
                        "준비 취소",
                        `/retention-reviews/${item.id}/transition`,
                        { expectedVersion: item.version, state: "DUE" },
                        "검토 대기로 되돌립니다. 원본이나 별도 보관본을 삭제하지 않습니다.",
                      )
                    }
                  >
                    준비 취소
                  </button>
                )}
              </>
            )}
          </li>
        ))}
      </ul>
      <button
        disabled={unavailable || offset === 0}
        onClick={() => setOffset(Math.max(0, offset - 20))}
      >
        이전 검토 페이지
      </button>
      <button
        disabled={unavailable || offset + 20 >= data.total}
        onClick={() => setOffset(offset + 20)}
      >
        다음 검토 페이지
      </button>
      <p>보관 완료·내보내기·자동 삭제는 아직 연결되지 않았습니다.</p>
      {message && <p role="status">{message}</p>}
      <RetentionEvents key={eventRefresh} />
      {command && (
        <RetentionCommand
          command={command}
          close={() => {
            setCommand(undefined);
            history.reload();
          }}
          done={(result) => {
            if (
              command.path === "/retention-company-hold" &&
              typeof result.version === "number"
            )
              onSettingsVersionChange?.(result.version);
            setCommand(undefined);
            setEventRefresh((value) => value + 1);
            setMessage(
              "added" in result
                ? `검토 ${String(result.added)}건 추가${result.hasMore ? " · 남은 대상은 다시 갱신하세요." : ""}`
                : "검토 상태를 저장했습니다. 원본은 변경하지 않았습니다.",
            );
            history.reload();
          }}
        />
      )}
    </section>
  );
}
function RetentionCommand({
  command,
  close,
  done,
}: {
  command: Command;
  close: () => void;
  done: (result: Record<string, unknown>) => void;
}) {
  const [reason, setReason] = useState("");
  const [agree, setAgree] = useState(false);
  const request = useSend();
  const guard = useDiscardGuard(Boolean(reason || agree));
  return (
    <FormPanel
      title={command.title}
      guard={guard}
      onClose={close}
      onSubmit={async (e) => {
        e.preventDefault();
        const result = await request.send<Record<string, unknown>>(
          command.path,
          "POST",
          { ...command.body, reason },
        );
        if (result) done(result);
      }}
      actions={
        <>
          <button
            disabled={request.pending || !agree || reason.trim().length < 2}
          >
            사유 확인하고 적용
          </button>
          <button
            type="button"
            disabled={request.pending}
            onClick={() => guard.guard(close)}
          >
            취소
          </button>
        </>
      }
    >
      <p>{command.notice}</p>
      <p>
        <Link to="/account/security" target="_blank" rel="noopener">
          내 계정 보안
        </Link>
        에서 본인 확인 후 5분 안에 적용하세요.
      </p>
      <ErrorNotice error={request.error} />
      <Field
        label="보관 검토 처리 사유"
        required
        minLength={2}
        maxLength={500}
        value={reason}
        disabled={request.pending}
        onChange={(e) => setReason(e.target.value)}
      />
      <p>
        사유에는 비공개 원문·개인정보를 넣지 마세요. 보안 관리자와 감사 담당자가
        조회하는 운영 기록입니다.
      </p>
      <label>
        <input
          type="checkbox"
          checked={agree}
          disabled={request.pending}
          onChange={(e) => setAgree(e.target.checked)}
        />
        처리 범위와 원본 유지 안내를 확인했습니다
      </label>
    </FormPanel>
  );
}

function RetentionEvents() {
  const [offset, setOffset] = useState(0);
  const events = useGet<{
    total: number;
    items: {
      id: string;
      action: string;
      entityId: string;
      reason: string;
      hold: boolean | null;
      from: string | null;
      to: string | null;
      at: string;
    }[];
  }>(`/retention-events?offset=${offset}&limit=20`);
  return (
    <section aria-label="보관 검토 변경 이력">
      <h3>보관 검토 변경 이력</h3>
      {events.error ? (
        <ErrorNotice error={events.error} retry={events.reload} />
      ) : !events.data ? (
        <Loading />
      ) : (
        <>
          <p>총 {events.data.total}건 · 최근 변경 순</p>
          <ul>
            {events.data.items.map((event) => (
              <li key={event.id}>
                {new Date(event.at).toLocaleString("ko-KR")} ·{" "}
                {event.action === "retention.company_hold.changed"
                  ? event.hold
                    ? "회사 보존 중지 적용"
                    : "회사 보존 중지 해제"
                  : event.action === "retention.state.changed"
                    ? `검토 #${event.entityId} · ${labels[event.from ?? ""] ?? event.from} → ${labels[event.to ?? ""] ?? event.to}`
                    : "검토 대상 갱신"}
                <p>사유: {event.reason}</p>
              </li>
            ))}
          </ul>
          {events.data.total === 0 && <p>보관 검토 변경 이력이 없습니다.</p>}
          <button
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - 20))}
          >
            이전 변경 이력 페이지
          </button>
          <button
            disabled={offset + 20 >= events.data.total}
            onClick={() => setOffset(offset + 20)}
          >
            다음 변경 이력 페이지
          </button>
        </>
      )}
    </section>
  );
}
