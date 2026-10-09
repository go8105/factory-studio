import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import {
  ErrorNotice,
  Field,
  PageTitle,
  useDiscardGuard,
  type DiscardGuard,
} from "../shared/components";
import { useGet, useRole, useSend, time, type HrPreview } from "./common";
import { NoRole, RoleBar } from "./ui";

function GuardNotice({ guard }: { guard: DiscardGuard }) {
  return guard.pending ? (
    <div role="alert">
      <p>저장하지 않은 변경이 있습니다.</p>
      <button type="button" onClick={guard.discard}>
        변경 버리기
      </button>
      <button type="button" onClick={guard.keep}>
        계속 편집
      </button>
    </div>
  ) : null;
}

function ConfirmButton({
  label,
  question,
  disabled,
  onConfirm,
}: {
  label: string;
  question: string;
  disabled: boolean;
  onConfirm: () => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" disabled={disabled} onClick={() => setOpen(true)}>
        {label}
      </button>
      {open && (
        <div role="alert">
          <p>{question}</p>
          <button
            type="button"
            disabled={disabled}
            onClick={() => {
              setOpen(false);
              onConfirm();
            }}
          >
            {label} 확인
          </button>
          <button
            type="button"
            disabled={disabled}
            onClick={() => setOpen(false)}
          >
            계속 유지
          </button>
        </div>
      )}
    </>
  );
}

type Comment = {
  id: string;
  authorId: string;
  authorName: string;
  body: string;
  status: string;
  version: number;
  createdAt: string;
  revisions: { revisionNo: number; body: string; createdAt: string }[];
};
export function Comments({
  kind,
  id,
  onDirty,
}: {
  kind: "POST" | "DOCUMENT";
  id: string;
  onDirty?: (dirty: boolean) => void;
}) {
  const { person } = useRole();
  return (
    <CommentSpace
      key={person + kind + id}
      kind={kind}
      id={id}
      onDirty={onDirty}
    />
  );
}
function CommentSpace({
  kind,
  id,
  onDirty,
}: {
  kind: "POST" | "DOCUMENT";
  id: string;
  onDirty?: (dirty: boolean) => void;
}) {
  const { person } = useRole();
  const list = useGet<Comment[]>(
    person
      ? `/comments?personId=${person}&targetKind=${kind}&targetId=${id}`
      : null,
  );
  const req = useSend();
  const [body, setBody] = useState("");
  const [edit, setEdit] = useState<Comment>();
  const [offset, setOffset] = useState(0);
  const more = useGet<Comment[]>(
    offset && person
      ? `/comments?personId=${person}&targetKind=${kind}&targetId=${id}&offset=${offset}`
      : null,
  );
  const guard = useDiscardGuard(!onDirty && !!body);
  useEffect(() => {
    onDirty?.(!!body);
    return () => onDirty?.(false);
  }, [body, onDirty]);
  async function save(e: FormEvent) {
    e.preventDefault();
    const r = await req.send(
      `/comments${edit ? "/" + edit.id : ""}`,
      edit ? "PATCH" : "POST",
      {
        actingPersonId: person,
        body,
        ...(edit
          ? { expectedVersion: edit.version }
          : { targetKind: kind, targetId: id }),
      },
    );
    if (r) {
      setBody("");
      setEdit(undefined);
      setOffset(0);
      list.reload();
    }
  }
  if (!person) return <p>댓글을 보려면 담당자를 선택하세요.</p>;
  const rows = offset ? more.data : list.data;
  return (
    <section className="gw-no-print">
      <h3>댓글</h3>
      <GuardNotice guard={guard} />
      <p className="muted">댓글은 기안 본문과 승인 범위를 바꾸지 않습니다.</p>
      <ErrorNotice error={list.error ?? more.error ?? req.error} />
      {rows?.map((c) => (
        <article className="gw-message" key={c.id}>
          <strong>{c.authorName}</strong> · {time(c.createdAt)}
          <p className="gw-body">
            {c.status === "DELETED" ? "삭제된 댓글입니다." : c.body}
          </p>
          {c.revisions.length > 0 && (
            <details>
              <summary>수정 이력 {c.revisions.length}건</summary>
              {c.revisions.map((r) => (
                <p key={r.revisionNo}>
                  {r.revisionNo}차 · {time(r.createdAt)}
                  <br />
                  {r.body}
                </p>
              ))}
            </details>
          )}
          {c.status === "ACTIVE" && c.authorId === person && (
            <div className="gw-actions">
              <button
                disabled={req.pending}
                onClick={() =>
                  guard.guard(() => {
                    setEdit(c);
                    setBody(c.body);
                  })
                }
              >
                댓글 수정
              </button>
              <ConfirmButton
                label="댓글 삭제"
                question="댓글을 삭제 표시할까요?"
                disabled={req.pending}
                onConfirm={() => {
                  void req
                    .send(`/comments/${c.id}/delete`, "POST", {
                      actingPersonId: person,
                      expectedVersion: c.version,
                    })
                    .then((r) => {
                      if (r) {
                        list.reload();
                        if (offset) more.reload();
                      }
                    });
                }}
              />
            </div>
          )}
        </article>
      ))}
      <div className="gw-actions">
        <button
          disabled={!offset}
          onClick={() => setOffset(Math.max(0, offset - 50))}
        >
          이전 댓글
        </button>
        <button
          disabled={rows?.length !== 50}
          onClick={() => setOffset(offset + 50)}
        >
          다음 댓글
        </button>
      </div>
      <form onSubmit={(e) => void save(e)}>
        <label>
          {edit ? "댓글 수정 내용" : "댓글 내용"}
          <textarea
            required
            maxLength={2000}
            value={body}
            disabled={req.pending}
            onChange={(e) => setBody(e.target.value)}
          />
        </label>
        <button disabled={req.pending}>
          {edit ? "수정 저장" : "댓글 등록"}
        </button>
        {edit && (
          <button
            type="button"
            onClick={() => {
              setEdit(undefined);
              setBody("");
            }}
          >
            수정 취소
          </button>
        )}
      </form>
    </section>
  );
}

type Notification = {
  id: string;
  kind: string;
  refKind: string;
  refId: string;
  title: string;
  readAt: string | null;
  createdAt: string;
};
export function Notifications() {
  const { person } = useRole();
  return <NotificationSpace key={person} />;
}
function NotificationSpace() {
  const { person } = useRole();
  const [offset, setOffset] = useState(0);
  const list = useGet<Notification[]>(
    person ? `/notifications?personId=${person}&offset=${offset}` : null,
  );
  const req = useSend();
  const labels: Record<string, string> = {
    APPROVAL_ARRIVED: "결재 도착",
    APPROVAL_DONE: "결재 완료",
    REJECTED: "반려",
    WITHDRAWN: "회수",
    NOTICE: "공지",
    COMMENT: "댓글",
    EVENT: "일정",
  };
  return (
    <div className="page-fill">
      <PageTitle id="G-12" title="알림함" help="gw/g-12" />
      <RoleBar />
      <ErrorNotice error={list.error ?? req.error} />
      {!person ? (
        <NoRole />
      ) : (
        <section>
          <button onClick={list.reload}>알림 새로고침</button>
          {list.data?.length === 0 && <p>표시할 알림이 없습니다.</p>}
          {list.data?.map((n) => (
            <article key={n.id} className="gw-message">
              <span>
                {n.readAt ? "읽음" : "안 읽음"} · {labels[n.kind] ?? n.kind} ·{" "}
                {time(n.createdAt)}
              </span>
              <h3>
                <Link
                  to={
                    (n.refKind === "POST"
                      ? "/gw/board"
                      : n.refKind === "EVENT"
                        ? "/gw/calendar"
                        : "/gw/documents") +
                    "?open=" +
                    n.refId
                  }
                >
                  {n.title}
                </Link>
              </h3>
              <button
                disabled={!!n.readAt || req.pending}
                onClick={() =>
                  void req
                    .send(`/notifications/${n.id}/read`, "POST", {
                      actingPersonId: person,
                    })
                    .then((r) => {
                      if (r) list.reload();
                    })
                }
              >
                읽음 표시
              </button>
            </article>
          ))}
          <div className="gw-actions">
            <button
              disabled={!offset}
              onClick={() => setOffset(Math.max(0, offset - 50))}
            >
              이전 알림
            </button>
            <button
              disabled={list.data?.length !== 50}
              onClick={() => setOffset(offset + 50)}
            >
              다음 알림
            </button>
          </div>
        </section>
      )}
    </div>
  );
}

type CalendarEvent = {
  id: string;
  eventNo: string;
  title: string;
  ownerId: string;
  ownerName: string;
  scope: string;
  organizationName: string | null;
  startsAt: string;
  endsAt: string;
  allDay: boolean;
  location: string | null;
  status: string;
  version: number;
  attendees: { personId: string; name: string; response: string }[];
};
const day = (d: Date) =>
  new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Seoul" }).format(d);
function dayDate(d: string) {
  return new Date(d + "T00:00:00+09:00");
}
function addDays(d: Date, n: number) {
  return new Date(d.getTime() + n * 86400000);
}
const local = (v: string) =>
  new Date(new Date(v).getTime() + 9 * 3600000).toISOString().slice(0, 16);
export function Calendar() {
  const { person } = useRole();
  return <CalendarSpace key={person} />;
}
function CalendarSpace() {
  const { person, people } = useRole();
  const [date, setDate] = useState(day(new Date()));
  const [mode, setMode] = useState("month");
  const [selected, setSelected] = useState<string | null>(
    new URLSearchParams(window.location.search).get("open"),
  );
  const [editing, setEditing] = useState(false);
  const d = dayDate(date);
  const start =
    mode === "month"
      ? dayDate(date.slice(0, 7) + "-01")
      : addDays(d, -d.getUTCDay());
  const end =
    mode === "month"
      ? dayDate(
          day(
            new Date(
              Date.UTC(Number(date.slice(0, 4)), Number(date.slice(5, 7)), 1) -
                9 * 3600000,
            ),
          ),
        )
      : addDays(start, 7);
  const list = useGet<CalendarEvent[]>(
    person
      ? `/calendar?personId=${person}&startsAt=${encodeURIComponent(start.toISOString())}&endsAt=${encodeURIComponent(end.toISOString())}`
      : null,
  );
  const detail = useGet<CalendarEvent>(
    person && selected ? `/calendar/${selected}?personId=${person}` : null,
  );
  const req = useSend();
  const [title, setTitle] = useState("");
  const [scope, setScope] = useState("PERSONAL");
  const [from, setFrom] = useState(date + "T09:00");
  const [to, setTo] = useState(date + "T10:00");
  const [allDay, setAllDay] = useState(false);
  const [location, setLocation] = useState("");
  const [attendees, setAttendees] = useState<string[]>([]);
  const guard = useDiscardGuard(editing);
  function edit(e?: CalendarEvent) {
    setTitle(e?.title ?? "");
    setScope(e?.scope ?? "PERSONAL");
    setFrom(e ? local(e.startsAt) : date + "T09:00");
    setTo(e ? local(e.endsAt) : date + "T10:00");
    setAllDay(e?.allDay ?? false);
    setLocation(e?.location ?? "");
    setAttendees(e?.attendees.map((a) => a.personId) ?? []);
    setEditing(true);
    if (!e) setSelected(null);
  }
  async function save(e: FormEvent) {
    e.preventDefault();
    const r = await req.send<CalendarEvent>(
      "/calendar" + (selected ? "/" + selected : ""),
      selected ? "PATCH" : "POST",
      {
        actingPersonId: person,
        title,
        scope,
        startsAt: new Date(from + "+09:00").toISOString(),
        endsAt: new Date(to + "+09:00").toISOString(),
        allDay,
        location: location || null,
        attendeeIds: attendees,
        ...(selected ? { expectedVersion: detail.data?.version } : {}),
      },
    );
    if (r) {
      setEditing(false);
      setSelected(r.id);
      detail.setData(r);
      list.reload();
    }
  }
  const days = Array.from(
    { length: Math.round((end.getTime() - start.getTime()) / 86400000) },
    (_, i) => addDays(start, i),
  );
  const ev = detail.data;
  return (
    <div className="page-fill">
      <PageTitle id="G-11" title="일정" help="gw/g-11" />
      <RoleBar guard={guard} pending={req.pending} />
      <GuardNotice guard={guard} />
      <ErrorNotice error={list.error ?? detail.error ?? req.error} />
      {!person ? (
        <NoRole />
      ) : (
        <>
          <div className="gw-actions">
            <Field
              label="기준일"
              type="date"
              value={date}
              onChange={(e) =>
                guard.guard(() => setDate(e.target.value || day(new Date())))
              }
            />
            <select
              aria-label="달력 보기"
              value={mode}
              onChange={(e) => guard.guard(() => setMode(e.target.value))}
            >
              <option value="month">월 보기</option>
              <option value="week">주 보기</option>
            </select>
            <button
              disabled={req.pending}
              onClick={() => guard.guard(() => edit())}
            >
              새 일정
            </button>
            <button onClick={list.reload}>일정 새로고침</button>
          </div>
          <p className="muted">
            한국 시간 기준. 개인 일정은 등록자·참석자, 부서 일정은 해당
            부서에서도 조회합니다.
          </p>
          <div className="gw-calendar">
            {mode === "month" &&
              Array.from({ length: start.getUTCDay() }, (_, i) => (
                <div className="gw-calendar-spacer" key={"space" + i} />
              ))}
            {days.map((date) => (
              <section key={day(date)} className="gw-day">
                <strong>
                  {day(date).slice(5)}{" "}
                  {new Intl.DateTimeFormat("ko-KR", {
                    timeZone: "Asia/Seoul",
                    weekday: "short",
                  }).format(date)}
                </strong>
                {list.data
                  ?.filter(
                    (e) =>
                      new Date(e.startsAt).getTime() <
                        addDays(date, 1).getTime() &&
                      new Date(e.endsAt).getTime() > date.getTime(),
                  )
                  .map((e) => (
                    <button
                      key={e.id}
                      onClick={() =>
                        guard.guard(() => {
                          setEditing(false);
                          setSelected(e.id);
                        })
                      }
                    >
                      {e.status === "CANCELLED" ? "[취소] " : ""}
                      {e.title}
                    </button>
                  ))}
              </section>
            ))}
          </div>
          {editing ? (
            <form onSubmit={(e) => void save(e)}>
              <h3>{selected ? "일정 수정" : "새 일정"}</h3>
              <fieldset disabled={req.pending}>
                <Field
                  label="일정 제목"
                  required
                  maxLength={200}
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
                <label>
                  공개 범위
                  <select
                    value={scope}
                    onChange={(e) => setScope(e.target.value)}
                  >
                    <option value="PERSONAL">개인</option>
                    <option value="DEPARTMENT">내 부서</option>
                  </select>
                </label>
                <Field
                  label="시작 (한국 시간)"
                  type="datetime-local"
                  required
                  value={from}
                  onChange={(e) => setFrom(e.target.value)}
                />
                <Field
                  label="끝 (한국 시간)"
                  type="datetime-local"
                  required
                  value={to}
                  onChange={(e) => setTo(e.target.value)}
                />
                <label className="inline-check">
                  <input
                    type="checkbox"
                    checked={allDay}
                    onChange={(e) => {
                      setAllDay(e.target.checked);
                      if (e.target.checked) {
                        setFrom(from.slice(0, 10) + "T00:00");
                        setTo(
                          day(addDays(dayDate(to.slice(0, 10)), 1)) + "T00:00",
                        );
                      }
                    }}
                  />
                  종일 (시작일 00:00~끝 다음 날 00:00)
                </label>
                <Field
                  label="장소"
                  maxLength={200}
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                />
                <fieldset>
                  <legend>참석자</legend>
                  {people
                    .filter((p) => p.isActive)
                    .map((p) => (
                      <label className="inline-check" key={p.id}>
                        <input
                          type="checkbox"
                          checked={attendees.includes(p.id)}
                          onChange={(e) =>
                            setAttendees(
                              e.target.checked
                                ? [...attendees, p.id]
                                : attendees.filter((id) => id !== p.id),
                            )
                          }
                        />
                        {p.name}
                      </label>
                    ))}
                </fieldset>
                <button>일정 저장</button>
                <button type="button" onClick={() => setEditing(false)}>
                  편집 취소
                </button>
              </fieldset>
            </form>
          ) : (
            ev && (
              <section className="gw-message">
                <h3>
                  {ev.title} {ev.status === "CANCELLED" && "(취소)"}
                </h3>
                <p>
                  {ev.eventNo} · {ev.ownerName} ·{" "}
                  {ev.scope === "PERSONAL" ? "개인" : ev.organizationName}
                </p>
                <p>
                  {time(ev.startsAt)} ~ {time(ev.endsAt)} ·{" "}
                  {ev.allDay ? "종일" : ""} {ev.location}
                </p>
                {ev.attendees.map((a) => (
                  <p key={a.personId}>
                    {a.name} ·{" "}
                    {
                      {
                        PENDING: "응답 대기",
                        ACCEPTED: "참석",
                        DECLINED: "불참",
                      }[a.response]
                    }
                  </p>
                ))}
                {ev.status === "ACTIVE" && (
                  <div className="gw-actions">
                    {ev.ownerId === person && (
                      <>
                        <button onClick={() => edit(ev)}>일정 수정</button>
                        <ConfirmButton
                          label="일정 취소"
                          question="일정을 취소할까요?"
                          disabled={req.pending}
                          onConfirm={() => {
                            void req
                              .send<CalendarEvent>(
                                `/calendar/${ev.id}/cancel`,
                                "POST",
                                {
                                  actingPersonId: person,
                                  expectedVersion: ev.version,
                                },
                              )
                              .then((r) => {
                                if (r) {
                                  detail.setData(r);
                                  list.reload();
                                }
                              });
                          }}
                        />
                      </>
                    )}
                    {ev.attendees.some((a) => a.personId === person) &&
                      ["ACCEPTED", "DECLINED"].map((response) => (
                        <button
                          key={response}
                          disabled={req.pending}
                          onClick={() =>
                            void req
                              .send<CalendarEvent>(
                                `/calendar/${ev.id}/respond`,
                                "POST",
                                {
                                  actingPersonId: person,
                                  expectedVersion: ev.version,
                                  response,
                                },
                              )
                              .then((r) => {
                                if (r) detail.setData(r);
                              })
                          }
                        >
                          {response === "ACCEPTED" ? "참석 응답" : "불참 응답"}
                        </button>
                      ))}
                  </div>
                )}
              </section>
            )
          )}
        </>
      )}
    </div>
  );
}

type Channel = {
  id: string;
  name: string;
  lastSeq: number;
  lastReadSeq: number;
};
type Message = {
  id: string;
  seq: number;
  authorId: string;
  authorName: string;
  body: string;
  createdAt: string;
};
type Thread = {
  channel: Channel;
  messages: Message[];
  members: { personId: string; name: string; leftAt: string | null }[];
  lastReadSeq: number;
};
export function Chat() {
  const { person } = useRole();
  return <ChatSpace key={person} />;
}
function ChatSpace() {
  const { person, people, busy } = useRole();
  const channels = useGet<Channel[]>(
    person ? `/channels?personId=${person}` : null,
  );
  const [selected, setSelected] = useState("");
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [kind, setKind] = useState("GROUP");
  const [members, setMembers] = useState<string[]>([]);
  const req = useSend();
  const [messageDirty, setMessageDirty] = useState(false);
  const guard = useDiscardGuard(creating || messageDirty);
  return (
    <div className="page-fill">
      <PageTitle id="G-13" title="채팅" help="gw/g-13" />
      <RoleBar guard={guard} pending={req.pending} />
      <GuardNotice guard={guard} />
      <ErrorNotice error={channels.error ?? req.error} />
      {!person ? (
        <NoRole />
      ) : (
        <>
          <button
            disabled={busy}
            onClick={() => guard.guard(() => setCreating(!creating))}
          >
            새 대화
          </button>
          {creating && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void req
                  .send<Channel>("/channels", "POST", {
                    actingPersonId: person,
                    name,
                    channelKind: kind,
                    memberIds: members,
                  })
                  .then((r) => {
                    if (r) {
                      setCreating(false);
                      setSelected(r.id);
                      channels.reload();
                    }
                  });
              }}
            >
              <Field
                label="대화 이름"
                required
                maxLength={100}
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
              <select
                aria-label="대화 구분"
                value={kind}
                onChange={(e) => setKind(e.target.value)}
              >
                <option value="GROUP">그룹 대화</option>
                <option value="DIRECT">1:1 대화</option>
              </select>
              <fieldset disabled={req.pending}>
                <legend>참여자 (나 포함)</legend>
                {people
                  .filter((p) => p.isActive && p.id !== person)
                  .map((p) => (
                    <label className="inline-check" key={p.id}>
                      <input
                        type="checkbox"
                        checked={members.includes(p.id)}
                        onChange={(e) =>
                          setMembers(
                            e.target.checked
                              ? [...members, p.id]
                              : members.filter((id) => id !== p.id),
                          )
                        }
                      />
                      {p.name}
                    </label>
                  ))}
                <button>대화 만들기</button>
              </fieldset>
            </form>
          )}
          <div className="gw-chat">
            <aside>
              <button onClick={channels.reload}>대화 목록 새로고침</button>
              {channels.data?.map((ch) => (
                <button
                  className="gw-channel"
                  key={ch.id}
                  disabled={busy}
                  onClick={() => guard.guard(() => setSelected(ch.id))}
                >
                  {ch.name} · 안 읽음 {ch.lastSeq - ch.lastReadSeq}
                </button>
              ))}
            </aside>
            {selected && (
              <Conversation
                key={selected}
                id={selected}
                onLeave={() => {
                  setSelected("");
                  channels.reload();
                }}
                guard={guard}
                onDirty={setMessageDirty}
                onRead={channels.reload}
              />
            )}
          </div>
        </>
      )}
    </div>
  );
}
function Conversation({
  id,
  onLeave,
  onRead,
  guard,
  onDirty,
}: {
  id: string;
  onLeave: () => void;
  onRead: () => void;
  guard: DiscardGuard;
  onDirty: (dirty: boolean) => void;
}) {
  const { person } = useRole();
  const [after, setAfter] = useState(0);
  const thread = useGet<Thread>(
    `/channels/${id}/messages?personId=${person}&after=${after}`,
  );
  const req = useSend();
  const [messages, setMessages] = useState<Message[]>([]);
  const [body, setBody] = useState("");
  const client = useRef<{ body: string; key: string } | undefined>(undefined);
  useEffect(() => {
    onDirty(!!body);
    return () => onDirty(false);
  }, [body, onDirty]);
  const last = messages.at(-1)?.seq ?? 0;
  useEffect(() => {
    if (!thread.data) return;
    setMessages((old) => {
      const map = new Map(old.map((m) => [m.seq, m]));
      thread.data!.messages.forEach((m) => map.set(m.seq, m));
      return [...map.values()].sort((a, b) => a.seq - b.seq);
    });
  }, [thread.data]);
  useEffect(() => {
    if (thread.error) return;
    const timer = window.setTimeout(() => {
      if (!req.pending && document.visibilityState === "visible") {
        setAfter(last);
        thread.reload();
      }
    }, 3000);
    return () => clearTimeout(timer);
  }, [thread.data, thread.error, req.pending, last]);
  async function send(e: FormEvent) {
    e.preventDefault();
    if (!client.current || client.current.body !== body)
      client.current = { body, key: crypto.randomUUID() };
    const r = await req.send(`/channels/${id}/messages`, "POST", {
      actingPersonId: person,
      body,
      clientKey: client.current.key,
    });
    if (r) {
      setBody("");
      client.current = undefined;
      thread.reload();
    }
  }
  return (
    <section>
      <h3>{thread.data?.channel.name ?? "대화"}</h3>
      <p>
        {thread.data?.members
          .map((m) => m.name + (m.leftAt ? " (나감)" : ""))
          .join(", ")}
      </p>
      <p className="muted">
        3초마다 새 메시지를 확인합니다. 오류가 나면 새로고침으로 다시
        연결하세요.
      </p>
      <ErrorNotice error={thread.error ?? req.error} />
      <button onClick={thread.reload}>메시지 새로고침</button>
      <ConfirmButton
        label="대화 나가기"
        question="대화를 나가면 메시지를 더 이상 볼 수 없습니다. 나갈까요?"
        disabled={req.pending}
        onConfirm={() =>
          guard.guard(() => {
            void req
              .send(`/channels/${id}/leave`, "POST", { actingPersonId: person })
              .then((r) => {
                if (r) onLeave();
              });
          })
        }
      />

      <div className="gw-messages" aria-live="polite">
        {messages.map((m) => (
          <article className="gw-message" key={m.id}>
            <strong>{m.authorName}</strong> · #{m.seq} · {time(m.createdAt)}
            <p className="gw-body">{m.body}</p>
          </article>
        ))}
      </div>
      {thread.data && last > thread.data.lastReadSeq && (
        <button
          disabled={req.pending}
          onClick={() =>
            void req
              .send(`/channels/${id}/read`, "POST", {
                actingPersonId: person,
                seq: last,
              })
              .then((r) => {
                if (r) {
                  thread.reload();
                  onRead();
                }
              })
          }
        >
          여기까지 읽음 표시
        </button>
      )}
      <form onSubmit={(e) => void send(e)}>
        <label>
          메시지
          <textarea
            required
            maxLength={2000}
            disabled={req.pending || !!thread.error}
            value={body}
            onChange={(e) => setBody(e.target.value)}
          />
        </label>
        <button disabled={req.pending || !!thread.error}>전송</button>
      </form>
    </section>
  );
}

export function Audience({
  visibility,
  org,
  onChange,
}: {
  visibility: string;
  org: string;
  onChange: (v: string, o: string) => void;
}) {
  const source = useGet<HrPreview>("/hr-preview");
  return (
    <>
      <label>
        공개 범위
        <select
          aria-label="공개 범위"
          value={visibility}
          onChange={(e) => onChange(e.target.value, "")}
        >
          <option value="WORKSPACE">전체 공간</option>
          <option value="ORG">부서 공지</option>
        </select>
      </label>
      {visibility === "ORG" && (
        <>
          <ErrorNotice error={source.error} />
          <label>
            대상 부서
            <select
              required
              value={org}
              onChange={(e) => onChange(visibility, e.target.value)}
            >
              <option value="">선택하세요</option>
              {source.data?.organizations
                .filter((o) => o.isActive)
                .map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.name}
                  </option>
                ))}
            </select>
          </label>
        </>
      )}
    </>
  );
}
