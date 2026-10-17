import { useState } from "react";
import { CompanyPeople } from "./Company";
import { GwLink as Link } from "./common";
import { MasterScreen, type MasterSpec } from "../shared/master";
import { ErrorNotice, Loading, PageTitle } from "../shared/components";
import {
  labels,
  time,
  useGet,
  useSend,
  useRole,
  type Department,
  type HrPreview,
} from "./common";

type Row = {
  id: string;
  code: string;
  name: string;
  jobRole: string;
  isActive: boolean;
  version: number;
  hrEmployeeCode: string | null;
  organizationName: string | null;
  hrStatus: string;
};
type Draft = { code: string; name: string; jobRole: string } & Record<
  string,
  unknown
>;
const hrLabels: Record<string, string> = {
  ACTIVE: "재직",
  RETIRED: "퇴직",
  RETIRE: "퇴직",
  LEAVE: "휴직",
  MISSING: "HR 원천 없음",
  UNAVAILABLE: "HR 조회 불가",
  UNLINKED: "수동 등록",
};
export function People() {
  const role = useRole();
  return role.companyId !== undefined ? <CompanyPeople /> : <PersonalPeople />;
}
function PersonalPeople() {
  const [revision, setRevision] = useState(0);
  const role = useRole();
  const spec: MasterSpec<Row, Draft> = {
    id: "G-07",
    title: "체험 담당자",
    help: "gw/g-07",
    base: "/api/v1/gw/people-master",
    allowDelete: false,
    reloadKey: revision,
    search: true,
    onSaved: role.reload,
    blank: { code: "", name: "", jobRole: "STAFF" },
    updateBody: (changes, row) => ({
      ...changes,
      expectedVersion: row.version,
    }),
    intro: (
      <>
        <p>
          합성 체험 역할입니다. HR 사원 코드는 실제 로그인 계정과 연결되지
          않습니다. HR 이름·부서는 가져오기로 갱신하며, GW 직무·활성 상태는 직접
          관리합니다. 상신 기록은 바뀌지 않습니다.
        </p>
        <HrImport
          done={() => {
            setRevision((n) => n + 1);
            role.reload();
          }}
        />
      </>
    ),
    columns: [
      { key: "code", label: "GW 코드" },
      { key: "name", label: "이름" },
      {
        key: "organizationName",
        label: "조직",
        render: (r) => r.organizationName ?? "미연결",
      },
      { key: "jobRole", label: "GW 직무", render: (r) => labels[r.jobRole] },
      {
        key: "hrEmployeeCode",
        label: "HR 사원 코드",
        render: (r) => r.hrEmployeeCode ?? "미연결",
      },
      {
        key: "hrStatus",
        label: "HR 상태",
        render: (r) => hrLabels[r.hrStatus] ?? r.hrStatus,
      },
      {
        key: "isActive",
        label: "GW 사용",
        render: (r) => (r.isActive ? "활성" : "비활성"),
      },
    ],
    fields: [
      {
        kind: "text",
        key: "code",
        label: "코드",
        required: true,
        pattern: String.raw`[A-Z][A-Z0-9\-]{1,29}`,
        maxLength: 30,
        upper: true,
      },
      {
        kind: "text",
        key: "name",
        label: "이름",
        required: true,
        maxLength: 80,
      },
      {
        kind: "select",
        key: "jobRole",
        label: "직무",
        options: Object.fromEntries(
          ["STAFF", "MANAGER", "EXECUTIVE", "BOARD_ADMIN"].map((k) => [
            k,
            labels[k],
          ]),
        ),
      },
    ],
    extra: (d, set) =>
      "isActive" in d ? (
        <label className="inline-check">
          <input
            type="checkbox"
            checked={!!d.isActive}
            onChange={(e) => set({ isActive: e.target.checked })}
          />
          GW 사용
        </label>
      ) : null,
    labels: {
      create: "담당자 등록",
      caption: "체험 담당자",
      emptyReason: "담당자를 등록하거나 HR에서 가져오세요.",
      editTitle: (r) => `${r.name} 수정`,
      deleted: (r) => `${r.name} 삭제`,
      moduleOff: "GW가 꺼져 있습니다.",
    },
  };
  // 공통 마스터에서 저장한 담당자도 역할 선택 목록에 반영한다.
  return <MasterScreen spec={spec} />;
}
function HrImport({ done }: { done: () => void }) {
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const [summary, setSummary] = useState("");
  const source = useGet<HrPreview>(open ? "/hr-preview" : null);
  const request = useSend();
  const data = source.data;
  const active = data?.employees?.filter((e) => e.status === "ACTIVE") ?? [];
  const linked = new Set(data?.people.map((p) => p.hrEmployeeCode));
  return (
    <section className="gw-hr-import" aria-label="HR에서 가져오기">
      <button
        className="secondary"
        disabled={request.pending}
        onClick={() => {
          setOpen(!open);
          setSelected([]);
        }}
      >
        HR에서 가져오기
      </button>
      {summary && <p role="status">{summary}</p>}
      {open && (
        <>
          <ErrorNotice error={source.error} retry={source.reload} />
          <ErrorNotice error={request.error} />
          {!data && !source.error && <Loading />}
          {data && !data.available && (
            <p>
              HR이 꺼져 있거나 아직 열지 않아 조회할 수 없습니다. 마지막 가져온
              정보는 유지합니다. <Link to="/hr">HR 열기</Link>
            </p>
          )}
          {data?.available && (
            <>
              <p>
                부서 {data.departments?.length ?? 0}개 전체와 선택한 재직 사원의
                이름·현재 부서를 가져옵니다. 신규 담당자의 GW 직무는 일반
                담당자입니다. 기존 GW 직무·활성 상태는 유지합니다. 선택하지 않은
                사원과 퇴직 사원은 자동으로 변경하지 않습니다. 한 번에 최대
                1,000명을 가져올 수 있습니다.
              </p>
              <details>
                <summary>가져올 부서 정보 확인</summary>
                <ul>
                  {data.departments?.map((d) => (
                    <li key={d.code}>
                      {d.name} · {d.code} ·{" "}
                      {d.parentCode ? `상위 ${d.parentCode}` : "최상위"} ·{" "}
                      {d.isActive ? "활성" : "비활성"}
                    </li>
                  ))}
                </ul>
              </details>
              <p>
                담당자 {selected.filter((c) => !linked.has(c)).length}명 신규 /{" "}
                {selected.filter((c) => linked.has(c)).length}명 갱신
              </p>
              {selected.length > 1000 && (
                <p role="alert">
                  한 번에 1,000명까지 선택할 수 있습니다. 나누어 가져오세요.
                </p>
              )}
              <fieldset disabled={request.pending}>
                <button
                  type="button"
                  className="link-button"
                  onClick={() => setSelected(active.map((e) => e.employeeCode))}
                >
                  재직 사원 전체 선택
                </button>
                <button
                  type="button"
                  className="link-button"
                  onClick={() => setSelected([])}
                >
                  선택 해제
                </button>
                <div className="gw-hr-list">
                  {active.map((e) => (
                    <label className="inline-check" key={e.employeeCode}>
                      <input
                        type="checkbox"
                        checked={selected.includes(e.employeeCode)}
                        onChange={(ev) =>
                          setSelected((s) =>
                            ev.target.checked
                              ? [...s, e.employeeCode]
                              : s.filter((c) => c !== e.employeeCode),
                          )
                        }
                      />
                      {e.name} · {e.employeeCode} · {e.departmentName} ·{" "}
                      {linked.has(e.employeeCode) ? "갱신" : "신규"}
                    </label>
                  ))}
                </div>
                {!active.length && (
                  <p>재직 사원이 없습니다. 부서만 가져올 수 있습니다.</p>
                )}
                <button
                  disabled={
                    !data.digest || request.pending || selected.length > 1000
                  }
                  onClick={async () => {
                    const result = await request.send<{
                      created: number;
                      updated: number;
                      departments: number;
                    }>("/import-hr", "POST", {
                      previewDigest: data.digest,
                      employeeCodes: selected,
                    });
                    if (result) {
                      setSummary(
                        `부서 ${result.departments}개, 담당자 신규 ${result.created}명·갱신 ${result.updated}명 반영했습니다.`,
                      );
                      setOpen(false);
                      done();
                    }
                  }}
                >
                  확인한 내용 가져오기
                </button>
                <button
                  className="secondary"
                  onClick={() => {
                    setSelected([]);
                    source.reload();
                  }}
                >
                  미리보기 다시 확인
                </button>
              </fieldset>
            </>
          )}
        </>
      )}
    </section>
  );
}

// 깊은 계층도 재귀 호출 없이 표시한다. 순환·고아 데이터는 무한 렌더 대신 오류로 알린다.
export function flattenTree(
  rows: Department[],
): { row: Department; depth: number }[] | null {
  const codes = new Set(rows.map((r) => r.code));
  if (
    codes.size !== rows.length ||
    rows.some((r) => r.parentCode && !codes.has(r.parentCode))
  )
    return null;
  const children = new Map<string | null, Department[]>();
  for (const row of rows)
    children.set(row.parentCode, [
      ...(children.get(row.parentCode) ?? []),
      row,
    ]);
  const stack = [...(children.get(null) ?? [])]
    .reverse()
    .map((row) => ({ row, depth: 0 }));
  const result: { row: Department; depth: number }[] = [];
  const visited = new Set<string>();
  while (stack.length) {
    const node = stack.pop()!;
    if (visited.has(node.row.code)) return null;
    visited.add(node.row.code);
    result.push(node);
    stack.push(
      ...(children.get(node.row.code) ?? [])
        .slice()
        .reverse()
        .map((row) => ({ row, depth: node.depth + 1 })),
    );
  }
  return result.length === rows.length ? result : null;
}
export function Organization() {
  const role = useRole();
  const source = useGet<HrPreview>("/hr-preview");
  const [snapshot, setSnapshot] = useState(false);
  const d = source.data;
  const ids = new Map(d?.organizations.map((o) => [o.id, o.code]));
  const rows = d
    ? snapshot || !d.available
      ? d.organizations.map((o) => ({
          code: o.code,
          name: o.name,
          parentCode: o.parentId ? (ids.get(o.parentId) ?? "상위 없음") : null,
          isActive: o.isActive,
          headEmployeeCode: null,
        }))
      : (d.departments ?? [])
    : [];
  const tree = flattenTree(rows);
  return (
    <div className="page-fill">
      <PageTitle
        id="G-10"
        title="조직도"
        help="gw/g-10"
        actions={
          <button className="secondary" onClick={source.reload}>
            새로고침
          </button>
        }
      />
      <p>
        {role.companyId !== undefined
          ? "회사 GW에 가져온 조직을 조회합니다. 조직 관리자는 현재 HR 조직과 대조할 수 있습니다."
          : "현재 HR 부서 계층을 읽기 전용으로 조회합니다."}{" "}
        GW 조직 반영은{" "}
        <Link to="/gw/people">
          {role.companyId !== undefined
            ? "회사 직원·연결·권한"
            : "체험 담당자 → HR에서 가져오기"}
        </Link>
        에서 진행하세요.
      </p>
      <ErrorNotice error={source.error} retry={source.reload} />
      {!d && !source.error && <Loading />}
      {d && (
        <>
          {!d.available && (
            <p role="status">
              {role.companyId !== undefined ? (
                "회사 GW에 가져온 조직입니다. 현재 HR과 대조·갱신은 GW 조직 관리자에게 문의하세요."
              ) : (
                <>
                  HR 조회 불가. 마지막 가져온 GW 조직을 표시합니다. 현재 HR
                  정보와 일치하는지는 확인할 수 없습니다.{" "}
                  <Link to="/hr">HR 열기</Link>
                </>
              )}
            </p>
          )}
          {d.available && (
            <label className="inline-check">
              <input
                type="checkbox"
                checked={snapshot}
                onChange={(e) => setSnapshot(e.target.checked)}
              />
              가져온 GW 조직 보기
            </label>
          )}
          <h2>
            {snapshot || !d.available ? "가져온 GW 조직" : "현재 HR 조직"}
          </h2>
          {!tree ? (
            <p role="alert">조직에 순환 또는 상위 부서 누락이 있습니다.</p>
          ) : !tree.length ? (
            <p>표시할 조직이 없습니다.</p>
          ) : (
            <ul className="gw-org-tree">
              {tree.map(({ row, depth }) => (
                <li
                  key={row.code}
                  style={{ paddingInlineStart: `${Math.min(depth, 5) * 12}px` }}
                >
                  <strong>{row.name}</strong> · {row.code} ·{" "}
                  {row.isActive ? "활성" : "비활성"}
                  <span className="muted">
                    {row.parentCode ? `상위 ${row.parentCode}` : "최상위"}
                    {row.headEmployeeCode
                      ? ` · 부서장 ${row.headEmployeeCode}`
                      : ""}
                  </span>
                  {(snapshot || !d.available) && (
                    <small>
                      가져온 시각:{" "}
                      {time(
                        d.organizations.find((o) => o.code === row.code)
                          ?.hrSyncedAt ?? null,
                      )}
                    </small>
                  )}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
