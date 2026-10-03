import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import {
  DataTable,
  ErrorNotice,
  Field,
  FormPanel,
  Loading,
  PageTitle,
  useDiscardGuard,
} from "../shared/components";
import { fieldErrors } from "../shared/hooks";
import {
  labels,
  useGet,
  useRole,
  useSend,
  type Page,
  type Person,
  type Route,
} from "./common";
import { RoleBar } from "./ui";
export function Masters({ kind }: { kind: "people" | "routes" }) {
  const [query, setQuery] = useSearchParams();
  const search = query.get("search") ?? "";
  const offset = Math.max(0, Number(query.get("offset")) || 0);
  const result = useGet<Page<Person | Route>>(
    `/${kind}?limit=20&offset=${offset}&search=${encodeURIComponent(search)}`,
  );
  const role = useRole();
  const [edit, setEdit] = useState<Person | Route | null | undefined>();
  const person = kind === "people";
  const title = person ? "체험 담당자" : "결재선 템플릿";
  return (
    <>
      <PageTitle
        id={person ? "G-07" : "G-06"}
        title={title}
        help={`gw/${person ? "g-07" : "g-06"}`}
        actions={<button onClick={() => setEdit(null)}>등록</button>}
      />
      <RoleBar />
      <p className="muted">
        {person
          ? "실제 계정이 아닌 합성 담당자입니다. 마지막 게시판 운영 담당자와 사용 중인 역할은 비활성화할 수 없습니다."
          : "템플릿 변경은 이미 기안된 문서에 자동 반영되지 않습니다. 초안에서 결재선을 다시 선택하세요."}
      </p>
      <Field
        label="검색"
        value={search}
        onChange={(e) => setQuery({ search: e.target.value })}
      />
      <ErrorNotice error={result.error} />
      {!result.data && !result.error ? (
        <Loading />
      ) : (
        result.data && (
          <DataTable
            rows={result.data.rows}
            columns={[
              { key: "code", label: "코드" },
              { key: "name", label: "이름" },
              {
                key: "isActive",
                label: "사용",
                render: (r) => (r.isActive ? "활성" : "비활성"),
              },
              {
                key: "id",
                label: "관리",
                render: (r) => (
                  <button className="link-button" onClick={() => setEdit(r)}>
                    편집
                  </button>
                ),
              },
            ]}
            caption={title}
            offset={offset}
            limit={20}
            total={result.data.total}
            onPage={(n) => setQuery({ search, offset: String(n) })}
          />
        )
      )}
      {edit !== undefined && (
        <MasterEditor
          key={edit?.id ?? "new"}
          kind={kind}
          value={edit}
          close={() => setEdit(undefined)}
          done={() => {
            setEdit(undefined);
            result.reload();
            role.reload();
          }}
        />
      )}
    </>
  );
}
function MasterEditor({
  kind,
  value,
  close,
  done,
}: {
  kind: "people" | "routes";
  value: Person | Route | null;
  close: () => void;
  done: () => void;
}) {
  const [code, setCode] = useState(value?.code ?? "");
  const [name, setName] = useState(value?.name ?? "");
  const [job, setJob] = useState(
    value && "jobRole" in value ? value.jobRole : "STAFF",
  );
  const [active, setActive] = useState(value?.isActive ?? true);
  const [steps, setSteps] = useState<string[]>(
    value && "steps" in value ? value.steps.map((s) => s.personId) : [""],
  );
  const { people } = useRole();
  const request = useSend();
  const errors = fieldErrors(request.error);
  const guard = useDiscardGuard(true);
  async function submit(e: FormEvent) {
    e.preventDefault();
    const base = value
      ? { expectedVersion: value.version, isActive: active }
      : { code };
    const body =
      kind === "people"
        ? { ...base, name, jobRole: job }
        : { ...base, name, steps: steps.map((personId) => ({ personId })) };
    if (
      await request.send(
        `/${kind}${value ? "/" + value.id : ""}`,
        value ? "PATCH" : "POST",
        body,
      )
    )
      done();
  }
  return (
    <FormPanel
      title={`${kind === "people" ? "담당자" : "결재선"} ${value ? "편집" : "등록"}`}
      guard={guard}
      onClose={() => {
        if (!request.pending) close();
      }}
      onSubmit={(e) => void submit(e)}
      actions={<button disabled={request.pending}>저장</button>}
    >
      <fieldset disabled={request.pending}>
        <ErrorNotice error={request.error} />
        <Field
          label="코드"
          required
          disabled={!!value}
          value={code}
          onChange={(e) => setCode(e.target.value)}
          error={errors["body.code"] ?? errors.code}
        />
        <Field
          label="이름"
          required
          maxLength={kind === "people" ? 80 : 100}
          value={name}
          onChange={(e) => setName(e.target.value)}
          error={errors["body.name"] ?? errors.name}
        />
        {kind === "people" ? (
          <label>
            직무
            <select value={job} onChange={(e) => setJob(e.target.value)}>
              {["STAFF", "MANAGER", "EXECUTIVE", "BOARD_ADMIN"].map((j) => (
                <option key={j} value={j}>
                  {labels[j]}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <>
            <h3>결재 순서 (1~3단계)</h3>
            {steps.map((id, i) => (
              <div className="gw-step" key={i}>
                <label>
                  {i + 1}단계
                  <select
                    aria-label={`${i + 1}단계 담당자`}
                    required
                    value={id}
                    onChange={(e) =>
                      setSteps((s) =>
                        s.map((v, j) => (j === i ? e.target.value : v)),
                      )
                    }
                  >
                    <option value="">담당자 선택</option>
                    {people
                      .filter((p) => p.isActive || p.id === id)
                      .map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name}
                          {!p.isActive ? " (비활성)" : ""}
                        </option>
                      ))}
                  </select>
                </label>
                <button
                  type="button"
                  disabled={i === 0}
                  onClick={() =>
                    setSteps((s) => {
                      const n = [...s];
                      [n[i - 1], n[i]] = [n[i], n[i - 1]];
                      return n;
                    })
                  }
                >
                  위로
                </button>
                <button
                  type="button"
                  disabled={i === steps.length - 1}
                  onClick={() =>
                    setSteps((s) => {
                      const n = [...s];
                      [n[i + 1], n[i]] = [n[i], n[i + 1]];
                      return n;
                    })
                  }
                >
                  아래로
                </button>
                <button
                  type="button"
                  disabled={steps.length === 1}
                  onClick={() => setSteps((s) => s.filter((_, j) => j !== i))}
                >
                  제거
                </button>
              </div>
            ))}
            <button
              type="button"
              disabled={steps.length >= 3}
              onClick={() => setSteps((s) => [...s, ""])}
            >
              단계 추가
            </button>
          </>
        )}
        {value && (
          <label>
            <input
              type="checkbox"
              checked={active}
              onChange={(e) => setActive(e.target.checked)}
            />{" "}
            활성
          </label>
        )}
      </fieldset>
    </FormPanel>
  );
}
