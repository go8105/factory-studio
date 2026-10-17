import { useEffect, useState } from "react";
import {
  ErrorNotice,
  Field,
  FormPanel,
  PageTitle,
  useDiscardGuard,
} from "../shared/components";
import {
  useGet,
  time,
  labels,
  SelectedPeople,
  useRole,
  useSend,
  type Person,
  type HrPreview,
} from "./common";

export type CompanyMe = {
  company: { id: number; name: string };
  person: (Person & { organizationUnitId?: string | null }) | null;
  bindingStatus: string;
  roles: string[];
  authzVersion: number;
  setupRequired: boolean;
  companyOwner: boolean;
  hrIdentityAvailable: boolean;
  businessReady: boolean;
};
type Binding = {
  id: string;
  personId: string;
  userId: string;
  state: string;
  version: number;
  code?: string;
  name?: string;
  hrEmployeeCode?: string;
  organizationName?: string;
};
export const companyRoles = [
  "ORG_ADMIN",
  "ROUTE_ADMIN",
  "POLICY_ADMIN",
  "BOARD_PUBLISHER",
  "SECURITY_ADMIN",
  "AUDITOR",
];
const bindingNames: Record<string, string> = {
  PENDING: "본인 확인 대기",
  ACTIVE: "연결 완료",
  SUSPENDED: "연결 정지",
  CANCELLED: "요청 취소",
};
function securityLabel(action: string) {
  if (action.includes("company-setup")) return "GW 최초 설정";
  if (action.includes("import-hr")) return "HR 직원 가져오기";
  if (action.includes("roles.")) return "GW 역할 변경";
  if (action.endsWith(".reader")) return "문서 읽기 권한 변경";
  if (action.endsWith(".step-reassigned")) return "미처리 결재 재배정";
  const operation = action.split(".").at(-1);
  return (
    (
      {
        request: "직원 연결 요청",
        accept: "본인 연결 동의",
        cancel: "미수락 요청 취소",
        suspend: "직원 연결 정지",
        resume: "동일 계정 복귀",
      } as Record<string, string>
    )[operation ?? ""] ?? "GW 보안 사건"
  );
}
export const roleNames: Record<string, string> = {
  ORG_ADMIN: "조직 관리",
  ROUTE_ADMIN: "결재선 관리",
  POLICY_ADMIN: "전결 관리",
  BOARD_PUBLISHER: "공지 게시",
  SECURITY_ADMIN: "보안 관리",
  AUDITOR: "보안 사건 조회",
};

export function CompanyStart({
  me,
  reload,
}: {
  me: CompanyMe;
  reload: () => void;
}) {
  const own = useGet<{
    employeeCode: string;
    name: string;
    departmentCode: string;
  }>(me.setupRequired && me.companyOwner ? "/company-setup" : null);
  const binding = useGet<Binding>(!me.setupRequired ? "/me/binding" : null);
  const [reason, setReason] = useState("");
  const [consent, setConsent] = useState(false);
  const request = useSend();
  const guard = useDiscardGuard(!!reason || consent);
  return (
    <section className="card">
      {guard.pending && (
        <div role="alert">
          <p>저장하지 않은 입력이 있습니다.</p>
          <button onClick={guard.discard}>변경 버리기</button>
          <button onClick={guard.keep}>계속 편집</button>
        </div>
      )}
      <PageTitle
        id="G-07"
        title={`${me.company.name} · 직원 연결`}
        help="gw/company"
      />
      <p>
        회사 GW는 로그인 계정에 연결된 본인 이름으로만 사용합니다. 회사 관리자와
        GW 업무 역할은 별개입니다.
      </p>
      <ErrorNotice error={request.error ?? own.error ?? binding.error} />
      {me.setupRequired ? (
        me.companyOwner ? (
          <>
            <p>
              빈 회사 GW의 최초 설정입니다. 본인 HR 직원 1명만 연결하고
              조직·결재선·전결·공지·보안 관리 역할을 부여합니다.
            </p>
            {own.data ? (
              <>
                <p>
                  {own.data.name} · {own.data.employeeCode} ·{" "}
                  {own.data.departmentCode}
                </p>
                <Field
                  label="최초 설정 사유"
                  value={reason}
                  maxLength={500}
                  onChange={(e) => setReason(e.target.value)}
                />
                <button
                  disabled={reason.trim().length < 2 || request.pending}
                  onClick={async () => {
                    if (
                      await request.send("/company-setup", "POST", {
                        employeeCode: own.data!.employeeCode,
                        reason,
                      })
                    )
                      reload();
                  }}
                >
                  확인한 본인으로 최초 설정
                </button>
              </>
            ) : (
              <p>
                본인 HR 직원 연결을 먼저 확인하세요. 임의 이름으로 대신 설정할
                수 없습니다.
              </p>
            )}
          </>
        ) : (
          <p>회사 소유자의 GW 최초 설정이 필요합니다.</p>
        )
      ) : binding.data?.state === "PENDING" ? (
        <>
          <p>
            {binding.data.name} · 사번 {binding.data.hrEmployeeCode} ·{" "}
            {binding.data.organizationName ?? "조직 미지정"}
          </p>
          <label>
            <input
              type="checkbox"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
            />
            위 사번·이름이 본인임을 확인했습니다.
          </label>
          <button
            disabled={!consent || request.pending}
            onClick={async () => {
              if (
                await request.send("/me/binding/accept", "POST", {
                  bindingId: binding.data!.id,
                  expectedVersion: binding.data!.version,
                })
              )
                reload();
            }}
          >
            본인 연결 동의
          </button>
        </>
      ) : (
        <p>
          {me.person && !me.person.isActive
            ? "GW 직원이 비활성 상태입니다. 회사 GW 조직 관리자에게 문의하세요."
            : me.bindingStatus === "SUSPENDED"
              ? "GW 연결이 정지되어 있습니다. 회사 GW 보안 관리자에게 문의하세요."
              : "GW 조직 관리자에게 직원 연결 요청을 문의하세요. 다른 직원의 연결은 대신 수락할 수 없습니다."}
        </p>
      )}
    </section>
  );
}

export function CompanyPeople() {
  const role = useRole();
  const orgAdmin = role.roles?.includes("ORG_ADMIN");
  const security = role.roles?.includes("SECURITY_ADMIN");
  const [search, setSearch] = useState("");
  const [editingPerson, setEditingPerson] = useState<Person>();
  const [offset, setOffset] = useState(0);
  const [bindingOffset, setBindingOffset] = useState(0);
  const [eventOffset, setEventOffset] = useState(0);
  const [candidateOffset, setCandidateOffset] = useState(0);
  const people = useGet<{ rows: Person[]; total: number }>(
    `/people?search=${encodeURIComponent(search)}&offset=${offset}&limit=20`,
  );
  const preview = useGet<HrPreview>(orgAdmin ? "/company-hr-preview" : null);
  const candidates = useGet<{
    items: { id: string; name: string }[];
    total: number;
  }>(
    orgAdmin
      ? `/identity-candidates?search=${encodeURIComponent(search)}&limit=50&offset=${candidateOffset}`
      : null,
  );
  const bindings = useGet<{ items: Binding[]; total: number }>(
    orgAdmin || security
      ? `/identity-bindings?limit=50&offset=${bindingOffset}`
      : null,
  );
  const [selectedCodes, setSelectedCodes] = useState<string[]>([]);
  const [personId, setPersonId] = useState("");
  const [userId, setUserId] = useState("");
  const [reason, setReason] = useState("");
  const [rolePerson, setRolePerson] = useState("");
  const grants = useGet<{ roles: string[]; version: number }>(
    security && rolePerson ? `/people/${rolePerson}/roles` : null,
  );
  const [nextRoles, setNextRoles] = useState<string[] | null>(null);
  const events = useGet<{
    items: { id: string; action: string; createdAt: string }[];
    total: number;
  }>(
    security || role.roles?.includes("AUDITOR")
      ? `/security-events?offset=${eventOffset}&limit=50`
      : null,
  );
  const request = useSend();
  const refresh = () => {
    people.reload();
    bindings.reload();
    preview.reload();
    grants.reload();
    events.reload();
    role.reload();
  };
  const guard = useDiscardGuard(
    !!reason ||
      !!personId ||
      !!userId ||
      selectedCodes.length > 0 ||
      nextRoles !== null,
  );
  const validReason = reason.trim().length >= 2;
  return (
    <section>
      <PageTitle id="G-07" title="회사 직원·연결·권한" help="gw/company" />
      {guard.pending && (
        <div role="alert">
          <p>저장하지 않은 입력이 있습니다.</p>
          <button onClick={guard.discard}>변경 버리기</button>
          <button onClick={guard.keep}>계속 편집</button>
        </div>
      )}
      <p>
        직원 이름·조직은 HR에서 명시적으로 가져옵니다. 직무 표시는 GW 권한을
        부여하지 않습니다. 활성 연결의 계정 교체는 제공하지 않습니다.
      </p>
      <Field
        label="직원·계정 이름 검색"
        value={search}
        onChange={(e) => {
          setSearch(e.target.value);
          setOffset(0);
        }}
        maxLength={100}
      />
      <ErrorNotice
        error={
          people.error ??
          bindings.error ??
          preview.error ??
          candidates.error ??
          events.error ??
          request.error
        }
      />
      <div className="table-scroll">
        <table>
          <caption>회사 GW 직원</caption>
          <thead>
            <tr>
              <th>사번</th>
              <th>직원</th>
              <th>활성</th>
              <th>관리</th>
            </tr>
          </thead>
          <tbody>
            {people.data?.rows.map((p) => (
              <tr key={p.id}>
                <td>{p.code}</td>
                <td>{p.name}</td>
                <td>{p.isActive ? "활성" : "비활성"}</td>
                <td>
                  {orgAdmin && (
                    <button onClick={() => setEditingPerson(p)}>
                      표시·활성 편집 · {p.name}
                    </button>
                  )}
                  {security && (
                    <button
                      onClick={() => {
                        setRolePerson(p.id);
                        setNextRoles(null);
                      }}
                    >
                      역할 확인 · {p.name}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button
        disabled={!offset}
        onClick={() => setOffset((v) => Math.max(0, v - 20))}
      >
        이전
      </button>
      <button
        disabled={offset + 20 >= (people.data?.total ?? 0)}
        onClick={() => setOffset((v) => v + 20)}
      >
        다음
      </button>
      {(orgAdmin || security) && (
        <Field
          label="변경 사유"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          maxLength={500}
        />
      )}
      {orgAdmin && (
        <section className="card">
          <h2>HR에서 직원 가져오기</h2>
          <p>
            미리보기의 재직 직원을 선택해 반영합니다. 계정 연결과 역할은 자동
            생성하지 않습니다.
          </p>
          {preview.data?.employees
            ?.filter((e) => e.status === "ACTIVE")
            .map((e) => (
              <label className="inline-check" key={e.employeeCode}>
                <input
                  type="checkbox"
                  checked={selectedCodes.includes(e.employeeCode)}
                  onChange={(ev) =>
                    setSelectedCodes((v) =>
                      ev.target.checked
                        ? [...v, e.employeeCode]
                        : v.filter((c) => c !== e.employeeCode),
                    )
                  }
                />
                {e.employeeCode} · {e.name} · {e.departmentName}
              </label>
            ))}
          <button
            disabled={!validReason || !preview.data?.digest || request.pending}
            onClick={async () => {
              if (
                await request.send("/company-hr-import", "POST", {
                  previewDigest: preview.data!.digest,
                  employeeCodes: selectedCodes,
                  reason,
                })
              ) {
                setSelectedCodes([]);
                refresh();
              }
            }}
          >
            선택한 직원 가져오기
          </button>
          <button onClick={preview.reload}>미리보기 다시 확인</button>
          <h2>본인 연결 요청</h2>
          <Pages
            name="회사 계정"
            offset={candidateOffset}
            total={candidates.data?.total ?? 0}
            limit={50}
            onChange={setCandidateOffset}
          />
          <label>
            GW 직원
            <select
              aria-label="연결할 GW 직원"
              value={personId}
              onChange={(e) => setPersonId(e.target.value)}
            >
              <option value="">선택</option>
              {people.data?.rows.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} · {p.code}
                </option>
              ))}
            </select>
          </label>
          <label>
            회사 계정
            <select
              aria-label="연결할 회사 계정"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
            >
              <option value="">선택</option>
              {candidates.data?.items.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.name} · {u.id}
                </option>
              ))}
            </select>
          </label>
          <button
            disabled={!personId || !userId || !validReason || request.pending}
            onClick={async () => {
              if (
                await request.send("/identity-bindings", "POST", {
                  personId,
                  userId,
                  reason,
                })
              )
                refresh();
            }}
          >
            직원에게 연결 동의 요청
          </button>
        </section>
      )}
      {(orgAdmin || security) && (
        <section className="card">
          <h2>연결 상태</h2>
          <Pages
            name="연결 상태"
            offset={bindingOffset}
            total={bindings.data?.total ?? 0}
            limit={50}
            onChange={setBindingOffset}
          />
          {bindings.data?.items.map((b) => (
            <div key={b.id}>
              <p>
                직원 {b.personId} · 계정 {b.userId} ·{" "}
                {bindingNames[b.state] ?? "상태 확인 필요"} · 버전 {b.version}
              </p>
              {((b.state === "PENDING" && orgAdmin) ||
                (b.state !== "PENDING" &&
                  b.state !== "CANCELLED" &&
                  security)) && (
                <button
                  disabled={!validReason || request.pending}
                  onClick={async () => {
                    const operation =
                      b.state === "PENDING"
                        ? "cancel"
                        : b.state === "ACTIVE"
                          ? "suspend"
                          : "resume";
                    if (
                      await request.send(
                        `/identity-bindings/${b.id}/${operation}`,
                        "POST",
                        { expectedVersion: b.version, reason },
                      )
                    )
                      refresh();
                  }}
                >
                  {b.state === "PENDING"
                    ? "미수락 요청 취소"
                    : b.state === "ACTIVE"
                      ? "연결 정지"
                      : "동일 계정 복귀"}
                </button>
              )}
            </div>
          ))}
        </section>
      )}
      {security && rolePerson && grants.data && (
        <section className="card">
          <h2>
            명시적 GW 역할 ·{" "}
            {people.data?.rows.find((p) => p.id === rolePerson)?.name ??
              rolePerson}
          </h2>
          {companyRoles.map((r) => (
            <label className="inline-check" key={r}>
              <input
                type="checkbox"
                checked={(nextRoles ?? grants.data!.roles).includes(r)}
                onChange={(e) =>
                  setNextRoles((v) =>
                    e.target.checked
                      ? [...(v ?? grants.data!.roles), r]
                      : (v ?? grants.data!.roles).filter((k) => k !== r),
                  )
                }
              />
              {roleNames[r]}
            </label>
          ))}
          <button
            disabled={!validReason || request.pending}
            onClick={async () => {
              if (
                await request.send(`/people/${rolePerson}/roles`, "PATCH", {
                  expectedVersion: grants.data!.version,
                  roles: nextRoles ?? grants.data!.roles,
                  reason,
                })
              ) {
                setNextRoles(null);
                refresh();
              }
            }}
          >
            역할 저장
          </button>
        </section>
      )}
      {events.data && (
        <section className="card">
          <h2>보안 사건</h2>
          <Pages
            name="보안 사건"
            offset={eventOffset}
            total={events.data.total}
            limit={50}
            onChange={setEventOffset}
          />
          <p>본문과 금액을 포함하지 않는 최소 사건 기록입니다.</p>
          {events.data.items.map((e) => (
            <p key={e.id}>
              {time(e.createdAt)} · {securityLabel(e.action)}
            </p>
          ))}
        </section>
      )}
      <BlockedAssignments reason={reason} />
      {editingPerson && (
        <PersonEditor
          person={editingPerson}
          close={() => setEditingPerson(undefined)}
          done={() => {
            setEditingPerson(undefined);
            refresh();
          }}
        />
      )}
    </section>
  );
}

function BlockedAssignments({ reason }: { reason: string }) {
  const role = useRole();
  const [offset, setOffset] = useState(0);
  const blocked = useGet<{
    items: {
      documentId: string;
      documentVersion: number;
      stepId: string;
      personId: string;
      seq: number;
    }[];
    total: number;
  }>(
    role.roles?.includes("SECURITY_ADMIN")
      ? `/blocked-assignments?limit=50&offset=${offset}`
      : null,
  );
  const [personId, setPersonId] = useState("");
  const req = useSend();
  if (!role.roles?.includes("SECURITY_ADMIN")) return null;
  return (
    <section className="card">
      <h2>막힌 결재 재배정</h2>
      <Pages
        name="막힌 결재"
        offset={offset}
        total={blocked.data?.total ?? 0}
        limit={50}
        onChange={setOffset}
      />
      <p>
        비활성 담당자의 미처리 단계만 변경합니다. 원 결재선과 처리 이력은
        보존하며, 본인·기안자·중복 참여자로 바꿀 수 없습니다.
      </p>
      <ErrorNotice error={blocked.error ?? req.error} />
      <label>
        새 담당자
        <select
          aria-label="재배정 직원"
          value={personId}
          onChange={(e) => setPersonId(e.target.value)}
        >
          <option value="">선택</option>
          {role.people.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </label>
      {blocked.data?.items.map((x) => (
        <p key={x.stepId}>
          문서 {x.documentId} · {x.seq}단계 · 담당 {x.personId}{" "}
          <button
            disabled={!personId || reason.trim().length < 2 || req.pending}
            onClick={async () => {
              if (
                await req.send(
                  `/documents/${x.documentId}/reassign-step`,
                  "POST",
                  {
                    expectedVersion: x.documentVersion,
                    stepId: x.stepId,
                    personId,
                    reason,
                  },
                )
              )
                blocked.reload();
            }}
          >
            미처리 단계 재배정
          </button>
        </p>
      ))}
    </section>
  );
}

export function DocumentReaders({
  documentId,
  version,
  onChanged,
  onDirty,
}: {
  documentId: string;
  version: number;
  onChanged: () => void;
  onDirty: (value: boolean) => void;
}) {
  const role = useRole();
  const [offset, setOffset] = useState(0);
  const readers = useGet<{
    items: { personId: string; isActive: boolean }[];
    total: number;
  }>(`/documents/${documentId}/readers?limit=100&offset=${offset}`);
  const [personId, setPersonId] = useState("");
  const [reason, setReason] = useState("");
  const req = useSend();
  useEffect(() => {
    onDirty(!!personId || !!reason);
    return () => onDirty(false);
  }, [personId, reason, onDirty]);
  async function save(target: string, isActive: boolean) {
    const saved = await req.send(
      `/documents/${documentId}/readers/${target}`,
      "PATCH",
      { expectedVersion: version, isActive, reason },
    );
    if (saved) {
      setReason("");
      setPersonId("");
      onChanged();
      readers.reload();
    }
  }
  return (
    <section className="card">
      <h3>문서 읽기 권한</h3>
      <Pages
        name="열람 직원"
        offset={offset}
        total={readers.data?.total ?? 0}
        limit={100}
        onChange={setOffset}
      />
      <p>
        상신한 문서의 기안자가 열람만 허용합니다. 읽기 권한은 승인·합의 권한을
        부여하지 않습니다.
      </p>
      <ErrorNotice error={readers.error ?? req.error} />
      <Field
        label="읽기 권한 변경 사유"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        maxLength={500}
      />
      <label>
        열람 직원
        <select
          aria-label="열람 직원"
          value={personId}
          onChange={(e) => setPersonId(e.target.value)}
        >
          <option value="">선택</option>
          <SelectedPeople ids={[personId]} />
          {role.people
            .filter((p) => p.isActive)
            .map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
        </select>
      </label>
      <button
        disabled={!personId || reason.trim().length < 2 || req.pending}
        onClick={async () => {
          const saved = await req.send(
            `/documents/${documentId}/readers`,
            "POST",
            { personId, expectedVersion: version, reason },
          );
          if (saved) {
            setReason("");
            setPersonId("");
            onChanged();
            readers.reload();
          }
        }}
      >
        읽기 권한 부여
      </button>
      {readers.data?.items
        .filter((r) => r.isActive)
        .map((r) => (
          <p key={r.personId}>
            직원 {r.personId} · 읽기 허용{" "}
            <button
              disabled={reason.trim().length < 2 || req.pending}
              onClick={() => void save(r.personId, false)}
            >
              읽기 권한 회수
            </button>
          </p>
        ))}
    </section>
  );
}

function Pages({
  name,
  offset,
  total,
  limit,
  onChange,
}: {
  name: string;
  offset: number;
  total: number;
  limit: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="gw-actions">
      <button
        disabled={!offset}
        onClick={() => onChange(Math.max(0, offset - limit))}
      >
        {name} 이전
      </button>
      <span>
        {total}건 · {Math.floor(offset / limit) + 1}쪽
      </span>
      <button
        disabled={offset + limit >= total}
        onClick={() => onChange(offset + limit)}
      >
        {name} 다음
      </button>
    </div>
  );
}

function PersonEditor({
  person,
  close,
  done,
}: {
  person: Person;
  close: () => void;
  done: () => void;
}) {
  const [job, setJob] = useState(person.jobRole);
  const [active, setActive] = useState(person.isActive);
  const [reason, setReason] = useState("");
  const req = useSend();
  const guard = useDiscardGuard(
    job !== person.jobRole || active !== person.isActive || !!reason,
  );
  return (
    <FormPanel
      title={`${person.name} · 표시·활성 편집`}
      guard={guard}
      onClose={close}
      onSubmit={async (e) => {
        e.preventDefault();
        if (
          await req.send(`/people-master/${person.id}`, "PATCH", {
            expectedVersion: person.version,
            jobRole: job,
            isActive: active,
            reason,
          })
        )
          done();
      }}
      actions={
        <button disabled={req.pending || reason.trim().length < 2}>
          직원 상태 저장
        </button>
      }
    >
      <p>
        {person.code} · {person.name}
      </p>
      <p>
        직원 이름·부서는 HR 가져오기로 갱신합니다. 직무 표시는 회사 GW 권한을
        부여하지 않습니다. 비활성 직원은 업무를 처리하지 못하며 마지막 활성 보안
        관리자는 보호합니다.
      </p>
      <ErrorNotice error={req.error} />
      <fieldset disabled={req.pending}>
        <label>
          직무 표시
          <select
            aria-label="GW 직무 표시"
            value={job}
            onChange={(e) => setJob(e.target.value)}
          >
            {["STAFF", "MANAGER", "EXECUTIVE", "BOARD_ADMIN"].map((k) => (
              <option key={k} value={k}>
                {labels[k]}
              </option>
            ))}
          </select>
        </label>
        <label className="inline-check">
          <input
            type="checkbox"
            checked={active}
            onChange={(e) => setActive(e.target.checked)}
          />
          GW 직원 활성
        </label>
        <Field
          label="직원 상태 변경 사유"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          minLength={2}
          maxLength={500}
          required
        />
      </fieldset>
    </FormPanel>
  );
}
