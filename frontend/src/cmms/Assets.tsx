// C-05 설비 대장 — 계층(라인 > 설비 > 구성품) 트리와 원천 가져오기 (UI-03 S 패턴 변형, FS-029 D46 · DSN-21 Q1·Q7).
// 가져온 설비는 원천 코드 1건당 1행이고, CMMS는 MES·BEMS를 읽기만 한다 — 저쪽을 바꾸지 않는다.
import { useState, type FormEvent } from "react";
import {
  Badge,
  DataTable,
  EmptyState,
  ErrorNotice,
  Field,
  FormPanel,
  Loading,
  PageTitle,
  useDiscardGuard,
  type Column,
} from "../shared/components";
import { ApiError } from "../shared/api";
import { useApiSend } from "../shared/hooks";
import { fieldErrors, moduleOff, useGet } from "./hooks";
import {
  ASSET_TYPE_LABEL,
  CMMS,
  CRITICALITY_LABEL,
  IMPORT_LABEL,
  SOURCE_LABEL,
  type Asset,
  type AssetNode,
  type AssetType,
  type Criticality,
  type ImportCandidate,
  type ImportSource,
} from "./common";

type Draft = {
  code: string;
  name: string;
  assetType: AssetType;
  location: string;
  parentAssetId: string;
  manufacturer: string;
  model: string;
  serialNo: string;
  installedOn: string;
  acquisitionCost: string;
  criticality: Criticality | "";
  isActive: boolean;
};
const blank: Draft = {
  code: "",
  name: "",
  assetType: "INJECTION",
  location: "",
  parentAssetId: "",
  manufacturer: "",
  model: "",
  serialNo: "",
  installedOn: "",
  acquisitionCost: "",
  criticality: "",
  isActive: true,
};
const orNull = (value: string) => (value.trim() === "" ? null : value.trim());
/** 가져온 설비는 원천이 이름·종류를 쥐고 있다. 여기서 고칠 수 있는 것은 상세·중요도·계층뿐이다. */
const IMPORTED_LOCK =
  "원천에서 가져온 설비라 코드·이름·종류는 바꿀 수 없습니다.";

function ImportPanel({
  onDone,
  onClose,
}: {
  onDone: () => void;
  onClose: () => void;
}) {
  const [source, setSource] = useState<ImportSource>("MES");
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const list = useGet<ImportCandidate[]>(
    `/assets/import-candidates?source=${source}`,
  );
  const { send, pending, error } = useApiSend(CMMS, () => {
    setPicked(new Set());
    list.reload();
    onDone();
  });
  // 고른 것이 있으면 패널을 닫기 전에 한 번 묻는다.
  const guard = useDiscardGuard(picked.size > 0);
  const sourceOff =
    list.error instanceof ApiError &&
    list.error.error.details?.reason === "SOURCE_MODULE_DISABLED";
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!picked.size) return;
    await send("/assets/import", "POST", {
      source,
      sourceCodes: [...picked],
    });
  }
  return (
    <FormPanel
      title="원천에서 가져오기"
      guard={guard}
      onClose={onClose}
      onSubmit={(e) => void submit(e)}
      actions={
        <>
          <button
            type="submit"
            disabled={pending || !picked.size}
            aria-busy={pending}
          >
            {picked.size ? `${picked.size}건 대장에 넣기` : "대장에 넣기"}
          </button>
          <button
            type="button"
            className="secondary"
            onClick={() => guard.guard(onClose)}
          >
            닫기
          </button>
        </>
      }
    >
      <p role="note" className="muted">
        원천 1건당 대장에 1행만 만듭니다. 이미 가져온 것은 목록에 나오지
        않습니다. 설비 코드는 원천 코드를 그대로 씁니다 — 두 쪽을 눈으로 맞출 수
        있어야 하기 때문입니다.
      </p>
      <div className="field">
        <label htmlFor="cmms-source">원천</label>
        <select
          id="cmms-source"
          value={source}
          onChange={(e) => {
            setSource(e.target.value as ImportSource);
            setPicked(new Set());
          }}
        >
          {(Object.keys(IMPORT_LABEL) as ImportSource[]).map((key) => (
            <option key={key} value={key}>
              {IMPORT_LABEL[key]}
            </option>
          ))}
        </select>
      </div>
      <ErrorNotice error={error} />
      {sourceOff ? (
        <p role="note" className="muted">
          {(list.error as ApiError).error.message}
        </p>
      ) : !list.data ? (
        !list.error && <Loading />
      ) : !list.data.length ? (
        <p className="muted">가져올 것이 없습니다. 이미 모두 가져왔습니다.</p>
      ) : (
        <fieldset className="field">
          <legend>가져올 대상</legend>
          {list.data.map((candidate) => (
            <label key={candidate.sourceCode} className="inline-check">
              <input
                type="checkbox"
                checked={picked.has(candidate.sourceCode)}
                onChange={(e) => {
                  const next = new Set(picked);
                  if (e.target.checked) next.add(candidate.sourceCode);
                  else next.delete(candidate.sourceCode);
                  setPicked(next);
                }}
              />
              {candidate.sourceCode} · {candidate.name}
              {candidate.note && (
                <small className="muted"> · {candidate.note}</small>
              )}
            </label>
          ))}
        </fieldset>
      )}
    </FormPanel>
  );
}

export function Assets() {
  const tree = useGet<AssetNode[]>("/assets/tree");
  const [edit, setEdit] = useState<Asset | "new" | null>(null);
  const [importing, setImporting] = useState(false);
  const [draft, setDraft] = useState<Draft>(blank);
  const [initial, setInitial] = useState<Draft>(blank);
  const { send, pending, error, setError } = useApiSend(CMMS, () =>
    tree.reload(),
  );
  const guard = useDiscardGuard(
    !!edit && JSON.stringify(draft) !== JSON.stringify(initial),
  );
  if (moduleOff(tree.error))
    return (
      <EmptyState
        reason="CMMS를 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다."
        to="/workspace"
        action="내 공간으로"
      />
    );
  const errors = fieldErrors(error);
  const imported = edit !== null && edit !== "new" && edit.source !== "CMMS";

  async function open(node: AssetNode) {
    const found = await fetch(`${CMMS}/assets/${node.id}`)
      .then((r) => r.json())
      .then((r) => r.data as Asset)
      .catch(() => null);
    if (!found) return;
    const values: Draft = {
      code: found.code,
      name: found.name,
      assetType: found.assetType,
      location: found.location ?? "",
      parentAssetId: found.parentAssetId ? String(found.parentAssetId) : "",
      manufacturer: found.manufacturer ?? "",
      model: found.model ?? "",
      serialNo: found.serialNo ?? "",
      installedOn: found.installedOn ?? "",
      acquisitionCost: found.acquisitionCost ?? "",
      criticality: found.criticality ?? "",
      isActive: found.isActive,
    };
    guard.guard(() => {
      setImporting(false);
      setEdit(found);
      setDraft(values);
      setInitial(values);
      setError(undefined);
    });
  }
  function start() {
    guard.guard(() => {
      setImporting(false);
      setEdit("new");
      setDraft(blank);
      setInitial(blank);
      setError(undefined);
    });
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!edit) return;
    const detail = {
      location: orNull(draft.location),
      parentAssetId: draft.parentAssetId ? Number(draft.parentAssetId) : null,
      manufacturer: orNull(draft.manufacturer),
      model: orNull(draft.model),
      serialNo: orNull(draft.serialNo),
      installedOn: orNull(draft.installedOn),
      acquisitionCost: orNull(draft.acquisitionCost),
      criticality: draft.criticality || null,
    };
    const saved =
      edit === "new"
        ? await send("/assets", "POST", {
            code: draft.code,
            name: draft.name,
            assetType: draft.assetType,
            ...detail,
          })
        : await send(`/assets/${edit.id}`, "PATCH", {
            ...(imported
              ? {}
              : { name: draft.name, assetType: draft.assetType }),
            isActive: draft.isActive,
            ...detail,
          });
    if (saved) setEdit(null);
  }
  const columns: Column<AssetNode>[] = [
    {
      key: "code",
      label: "설비",
      render: (n) => (
        <span style={{ paddingLeft: `${n.depth * 16}px` }}>
          {n.depth > 0 && <span aria-hidden="true">└ </span>}
          <button
            type="button"
            className="link-button"
            onClick={() => void open(n)}
          >
            {n.code}
          </button>{" "}
          {n.name}
        </span>
      ),
    },
    {
      key: "assetType",
      label: "종류",
      render: (n) => ASSET_TYPE_LABEL[n.assetType],
    },
    { key: "location", label: "위치", render: (n) => n.location ?? "—" },
    {
      key: "source",
      label: "출처",
      render: (n) => SOURCE_LABEL[n.source],
    },
    {
      key: "criticality",
      label: "중요도",
      render: (n) =>
        n.criticality ? (
          <Badge tone={n.criticality === "A" ? "issue" : "normal"}>
            {n.criticality}
          </Badge>
        ) : (
          <span className="muted">—</span>
        ),
    },
    {
      key: "isActive",
      label: "사용",
      render: (n) =>
        n.isActive ? (
          <Badge>사용</Badge>
        ) : (
          <Badge tone="warning">사용 안 함</Badge>
        ),
    },
  ];
  const parents = (tree.data ?? []).filter(
    (n) => edit === "new" || (edit !== null && n.id !== edit.id),
  );
  return (
    <div className="page-fill">
      <PageTitle
        id="C-05"
        title="설비 대장"
        subtitle="보전 대상 설비를 등록하거나 MES·BEMS에서 가져옵니다"
        help="cmms/c-05"
        actions={
          <>
            <button
              type="button"
              aria-pressed={importing}
              onClick={() =>
                guard.guard(() => (setEdit(null), setImporting(true)))
              }
            >
              가져오기
            </button>{" "}
            <button type="button" aria-pressed={edit === "new"} onClick={start}>
              설비 등록
            </button>
          </>
        }
      />
      <ErrorNotice error={tree.error} retry={() => tree.reload()} />
      {!tree.data ? (
        !tree.error && <Loading />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <DataTable
              rows={tree.data}
              columns={columns}
              caption="설비 대장(계층 순)"
              offset={0}
              total={tree.data.length}
              limit={tree.data.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="설비가 없습니다. 직접 등록하거나 MES·BEMS에서 가져오세요."
                  action="설비 등록"
                  onAction={start}
                />
              }
            />
          </section>
          {importing ? (
            <ImportPanel
              onDone={() => tree.reload()}
              onClose={() => setImporting(false)}
            />
          ) : (
            edit && (
              <FormPanel
                key={edit === "new" ? "new" : edit.id}
                title={edit === "new" ? "설비 등록" : `${edit.code} 수정`}
                guard={guard}
                onClose={() => setEdit(null)}
                onSubmit={(e) => void submit(e)}
                actions={
                  <>
                    <button
                      type="submit"
                      disabled={pending}
                      aria-busy={pending}
                    >
                      {edit === "new" ? "등록" : "저장"}
                    </button>
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => guard.guard(() => setEdit(null))}
                    >
                      취소
                    </button>
                  </>
                }
              >
                <ErrorNotice
                  error={Object.keys(errors).length ? undefined : error}
                />
                {imported && (
                  <p role="note" className="muted">
                    {IMPORTED_LOCK} 상세·중요도·계층은 CMMS에서 정합니다.
                  </p>
                )}
                <Field
                  label="설비 코드"
                  value={draft.code}
                  required
                  disabled={edit !== "new"}
                  pattern="[A-Z][A-Z0-9\-]{1,19}"
                  title="영문 대문자로 시작하는 2~20자"
                  error={errors.code}
                  onChange={(e) =>
                    setDraft({ ...draft, code: e.target.value.toUpperCase() })
                  }
                />
                <Field
                  label="설비명"
                  value={draft.name}
                  required
                  maxLength={100}
                  disabled={imported}
                  error={errors.name}
                  onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                />
                <div className="field">
                  <label htmlFor="cmms-type">종류</label>
                  <select
                    id="cmms-type"
                    value={draft.assetType}
                    disabled={imported}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        assetType: e.target.value as AssetType,
                      })
                    }
                  >
                    {(Object.keys(ASSET_TYPE_LABEL) as AssetType[]).map((k) => (
                      <option key={k} value={k}>
                        {ASSET_TYPE_LABEL[k]}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label htmlFor="cmms-parent">상위 설비</label>
                  <select
                    id="cmms-parent"
                    value={draft.parentAssetId}
                    aria-invalid={!!errors.parentAssetId}
                    onChange={(e) =>
                      setDraft({ ...draft, parentAssetId: e.target.value })
                    }
                  >
                    <option value="">없음(최상위)</option>
                    {parents.map((n) => (
                      <option key={n.id} value={n.id}>
                        {" ".repeat(n.depth * 2)}
                        {n.code} {n.name}
                      </option>
                    ))}
                  </select>
                  {errors.parentAssetId && (
                    <small>{errors.parentAssetId}</small>
                  )}
                </div>
                <div className="field">
                  <label htmlFor="cmms-criticality">중요도</label>
                  <select
                    id="cmms-criticality"
                    value={draft.criticality}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        criticality: e.target.value as Criticality | "",
                      })
                    }
                  >
                    <option value="">정하지 않음</option>
                    {(Object.keys(CRITICALITY_LABEL) as Criticality[]).map(
                      (k) => (
                        <option key={k} value={k}>
                          {CRITICALITY_LABEL[k]}
                        </option>
                      ),
                    )}
                  </select>
                </div>
                <Field
                  label="위치"
                  value={draft.location}
                  maxLength={100}
                  onChange={(e) =>
                    setDraft({ ...draft, location: e.target.value })
                  }
                />
                <Field
                  label="제조사"
                  value={draft.manufacturer}
                  maxLength={100}
                  onChange={(e) =>
                    setDraft({ ...draft, manufacturer: e.target.value })
                  }
                />
                <Field
                  label="모델"
                  value={draft.model}
                  maxLength={100}
                  onChange={(e) =>
                    setDraft({ ...draft, model: e.target.value })
                  }
                />
                <Field
                  label="일련번호"
                  value={draft.serialNo}
                  maxLength={60}
                  onChange={(e) =>
                    setDraft({ ...draft, serialNo: e.target.value })
                  }
                />
                <Field
                  label="설치일"
                  type="date"
                  value={draft.installedOn}
                  onChange={(e) =>
                    setDraft({ ...draft, installedOn: e.target.value })
                  }
                />
                <Field
                  label="취득가"
                  value={draft.acquisitionCost}
                  inputMode="decimal"
                  pattern="\d{1,16}(\.\d{1,2})?"
                  error={errors.acquisitionCost}
                  onChange={(e) =>
                    setDraft({ ...draft, acquisitionCost: e.target.value })
                  }
                />
                {edit !== "new" && (
                  <label className="inline-check">
                    <input
                      type="checkbox"
                      checked={draft.isActive}
                      onChange={(e) =>
                        setDraft({ ...draft, isActive: e.target.checked })
                      }
                    />
                    사용
                  </label>
                )}
              </FormPanel>
            )
          )}
        </div>
      )}
    </div>
  );
}
