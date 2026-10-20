// C-04 예방보전 계획 — 주기가 되면 사람이 PM 작업지시를 만든다 (FS-029 D49 · DSN-21 Q2·Q3).
// 자동 생성은 없다. "주기가 됐다"는 것과 "지금 세워도 된다"는 다른 판단이기 때문이다.
import { useState, type FormEvent } from "react";
import {
  Badge,
  DataTable,
  DetailPanel,
  EmptyState,
  ErrorNotice,
  Field,
  FormPanel,
  Loading,
  PageTitle,
  useDiscardGuard,
  type Column,
} from "../shared/components";
import { useApiSend } from "../shared/hooks";
import { fieldErrors, moduleOff, useGet } from "./hooks";
import {
  CMMS,
  METHOD_LABEL,
  TRIGGER_LABEL,
  TRIGGER_UNIT,
  qty,
  standardOf,
  type AssetNode,
  type CheckMethod,
  type PmPlan,
  type TriggerKind,
} from "./common";

type Draft = {
  assetId: string;
  code: string;
  title: string;
  triggerKind: TriggerKind;
  intervalDays: string;
  intervalUsage: string;
  startOn: string;
};
type ItemDraft = {
  name: string;
  method: CheckMethod;
  standardText: string;
  lowerLimit: string;
  upperLimit: string;
  unit: string;
};
const blankItem: ItemDraft = {
  name: "",
  method: "OK_NG",
  standardText: "",
  lowerLimit: "",
  upperLimit: "",
  unit: "",
};
const today = () => new Date().toISOString().slice(0, 10);
const orNull = (v: string) => (v.trim() === "" ? null : v.trim());

function PlanDetail({
  plan,
  onChanged,
}: {
  plan: PmPlan;
  onChanged: () => void;
}) {
  const detail = useGet<PmPlan>(`/pm-plans/${plan.id}`);
  const [item, setItem] = useState<ItemDraft>(blankItem);
  const [made, setMade] = useState("");
  const { send, pending, error } = useApiSend(CMMS, () => {
    detail.reload();
    onChanged();
  });
  const errors = fieldErrors(error);
  if (!detail.data)
    return detail.error ? <ErrorNotice error={detail.error} /> : <Loading />;
  const row = detail.data;
  const items = row.items ?? [];
  async function addItem(event: FormEvent) {
    event.preventDefault();
    const saved = await send(`/pm-plans/${plan.id}/items`, "POST", {
      name: item.name,
      method: item.method,
      standardText: orNull(item.standardText),
      lowerLimit: item.method === "RANGE" ? orNull(item.lowerLimit) : null,
      upperLimit: item.method === "RANGE" ? orNull(item.upperLimit) : null,
      unit: item.method === "RANGE" ? orNull(item.unit) : null,
    });
    if (saved) setItem(blankItem);
  }
  async function makeOrder() {
    const saved = await send<{ woNo: string }>(
      `/pm-plans/${plan.id}/work-order`,
      "POST",
      {},
    );
    if (saved) setMade(`${saved.woNo} 작업지시를 만들었습니다.`);
  }
  return (
    <>
      <p className="muted">
        {row.assetCode} · {row.assetName} · {TRIGGER_LABEL[row.triggerKind]}{" "}
        {row.triggerKind === "CALENDAR"
          ? `${row.intervalDays}일`
          : `${qty(row.intervalUsage)}${TRIGGER_UNIT[row.triggerKind]}`}
      </p>
      <dl className="spc-figures">
        <dt>시작일</dt>
        <dd>{row.startOn}</dd>
        <dt>마지막 수행</dt>
        <dd>{row.lastDoneOn ?? "없음"}</dd>
        {row.triggerKind === "CALENDAR" ? (
          <>
            <dt>다음 예정일</dt>
            <dd>{row.dueOn}</dd>
          </>
        ) : (
          <>
            <dt>지금까지</dt>
            <dd>
              {row.unknown
                ? "모름"
                : `${qty(row.usageNow)}${TRIGGER_UNIT[row.triggerKind]}`}
            </dd>
            <dt>마지막 수행 뒤</dt>
            <dd>
              {row.unknown
                ? "모름"
                : `${qty(row.usageSinceLast)}${TRIGGER_UNIT[row.triggerKind]}`}
            </dd>
          </>
        )}
      </dl>
      <p role="status">{made}</p>
      <ErrorNotice error={Object.keys(errors).length ? undefined : error} />
      {row.unknown ? (
        <p role="note" className="muted">
          MES를 사용하지 않도록 설정해 사용량을 읽을 수 없습니다. 도래를 판정할
          수 없어 작업지시를 만들 수 없습니다.
        </p>
      ) : (
        <p>
          <button
            type="button"
            disabled={pending || !row.isDue || !row.isActive}
            aria-busy={pending}
            title={!row.isDue ? "아직 주기가 되지 않았습니다." : undefined}
            onClick={() => void makeOrder()}
          >
            PM 작업지시 만들기
          </button>
        </p>
      )}
      <section>
        <h3>점검 항목</h3>
        {items.length ? (
          <ul className="spc-trend">
            {items.map((i) => (
              <li key={i.id}>
                <strong>
                  {i.seq}. {i.name}
                </strong>
                <span>{standardOf(i)}</span>
                <small className="muted">
                  {METHOD_LABEL[i.method]}
                  {!i.isActive && " · 사용 안 함"}
                </small>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">
            점검 항목이 없습니다. 없으면 점검 없이 바로 완료할 수 있습니다.
          </p>
        )}
        <form className="spc-resolve" onSubmit={(e) => void addItem(e)}>
          <Field
            label="항목 이름"
            value={item.name}
            required
            maxLength={100}
            error={errors.name}
            onChange={(e) => setItem({ ...item, name: e.target.value })}
          />
          <div className="field">
            <label htmlFor="pm-method">판정 방법</label>
            <select
              id="pm-method"
              value={item.method}
              onChange={(e) =>
                setItem({ ...item, method: e.target.value as CheckMethod })
              }
            >
              {(Object.keys(METHOD_LABEL) as CheckMethod[]).map((k) => (
                <option key={k} value={k}>
                  {METHOD_LABEL[k]}
                </option>
              ))}
            </select>
          </div>
          {item.method === "RANGE" ? (
            <>
              <Field
                label="하한(선택)"
                value={item.lowerLimit}
                inputMode="decimal"
                error={errors.lowerLimit}
                onChange={(e) =>
                  setItem({ ...item, lowerLimit: e.target.value })
                }
              />
              <Field
                label="상한(선택)"
                value={item.upperLimit}
                inputMode="decimal"
                onChange={(e) =>
                  setItem({ ...item, upperLimit: e.target.value })
                }
              />
              <Field
                label="단위"
                value={item.unit}
                required
                maxLength={10}
                onChange={(e) => setItem({ ...item, unit: e.target.value })}
              />
            </>
          ) : (
            <Field
              label="기준(선택)"
              value={item.standardText}
              maxLength={200}
              onChange={(e) =>
                setItem({ ...item, standardText: e.target.value })
              }
            />
          )}
          <button type="submit" disabled={pending} aria-busy={pending}>
            항목 추가
          </button>
        </form>
      </section>
    </>
  );
}

export function PmPlans() {
  const list = useGet<PmPlan[]>("/pm-plans");
  const assets = useGet<AssetNode[]>("/assets/tree");
  const [open, setOpen] = useState<PmPlan | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const { send, pending, error, setError } = useApiSend(CMMS, () =>
    list.reload(),
  );
  const guard = useDiscardGuard(!!draft && draft.title.trim() !== "");
  if (moduleOff(list.error))
    return (
      <EmptyState
        reason="CMMS를 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다."
        to="/workspace"
        action="내 공간으로"
      />
    );
  const errors = fieldErrors(error);
  const live = (assets.data ?? []).filter((a) => a.isActive);
  // 사용량 기준은 MES에서 가져온 설비·금형에만 쓸 수 있다.
  const fromSource = draft
    ? live.find((a) => String(a.id) === draft.assetId)?.sourceCode != null
    : false;

  function start() {
    guard.guard(() => {
      setOpen(null);
      setError(undefined);
      setDraft({
        assetId: String(live[0]?.id ?? ""),
        code: "",
        title: "",
        triggerKind: "CALENDAR",
        intervalDays: "30",
        intervalUsage: "",
        startOn: today(),
      });
    });
  }
  async function create(event: FormEvent) {
    event.preventDefault();
    if (!draft) return;
    const calendar = draft.triggerKind === "CALENDAR";
    const saved = await send<PmPlan>("/pm-plans", "POST", {
      assetId: Number(draft.assetId),
      code: draft.code,
      title: draft.title,
      triggerKind: draft.triggerKind,
      intervalDays: calendar ? Number(draft.intervalDays) : null,
      intervalUsage: calendar ? null : draft.intervalUsage,
      startOn: draft.startOn,
    });
    if (saved) {
      setDraft(null);
      setOpen(saved);
    }
  }
  const columns: Column<PmPlan>[] = [
    { key: "code", label: "코드" },
    {
      key: "id",
      label: "관리",
      render: (p) => (
        <button
          type="button"
          className="link-button"
          aria-pressed={open?.id === p.id}
          onClick={() =>
            guard.guard(() => {
              setDraft(null);
              setOpen(p);
              setError(undefined);
            })
          }
        >
          상세
        </button>
      ),
    },
    {
      key: "assetCode",
      label: "설비",
      render: (p) => `${p.assetCode} ${p.assetName}`,
    },
    { key: "title", label: "제목" },
    {
      key: "triggerKind",
      label: "기준",
      render: (p) =>
        `${TRIGGER_LABEL[p.triggerKind]} ${
          p.triggerKind === "CALENDAR"
            ? `${p.intervalDays}일`
            : `${qty(p.intervalUsage)}${TRIGGER_UNIT[p.triggerKind]}`
        }`,
    },
    {
      key: "dueOn",
      label: "도래",
      render: (p) =>
        p.unknown ? (
          <span className="muted">모름(MES 꺼짐)</span>
        ) : p.isDue ? (
          <Badge tone="issue">도래</Badge>
        ) : p.triggerKind === "CALENDAR" ? (
          p.dueOn
        ) : (
          `${qty(p.usageSinceLast)}/${qty(p.intervalUsage)}${TRIGGER_UNIT[p.triggerKind]}`
        ),
    },
    {
      key: "lastDoneOn",
      label: "마지막 수행",
      render: (p) => p.lastDoneOn ?? "—",
    },
    {
      key: "isActive",
      label: "사용",
      render: (p) =>
        p.isActive ? (
          <Badge>사용</Badge>
        ) : (
          <Badge tone="warning">사용 안 함</Badge>
        ),
    },
  ];
  return (
    <div className="page-fill">
      <PageTitle
        id="C-04"
        title="예방보전 계획"
        subtitle="주기가 되면 PM 작업지시를 만듭니다. 자동 생성은 없습니다"
        help="cmms/c-04"
        actions={
          <button
            type="button"
            aria-pressed={!!draft}
            disabled={!live.length}
            title={!live.length ? "설비 대장이 비어 있습니다." : undefined}
            onClick={start}
          >
            계획 등록
          </button>
        }
      />
      <ErrorNotice error={list.error} retry={() => list.reload()} />
      {!list.data ? (
        !list.error && <Loading />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <DataTable
              rows={list.data}
              columns={columns}
              caption="예방보전 계획"
              offset={0}
              total={list.data.length}
              limit={list.data.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="예방보전 계획이 없습니다."
                  action="계획 등록"
                  onAction={start}
                />
              }
            />
          </section>
          {draft ? (
            <FormPanel
              title="예방보전 계획 등록"
              guard={guard}
              onClose={() => setDraft(null)}
              onSubmit={(e) => void create(e)}
              actions={
                <>
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    등록
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => guard.guard(() => setDraft(null))}
                  >
                    취소
                  </button>
                </>
              }
            >
              <ErrorNotice
                error={Object.keys(errors).length ? undefined : error}
              />
              <div className="field">
                <label htmlFor="pm-asset">설비</label>
                <select
                  id="pm-asset"
                  value={draft.assetId}
                  onChange={(e) =>
                    setDraft({ ...draft, assetId: e.target.value })
                  }
                >
                  {live.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.code} {a.name}
                    </option>
                  ))}
                </select>
              </div>
              <Field
                label="계획 코드"
                value={draft.code}
                required
                pattern="[A-Z][A-Z0-9\-]{1,19}"
                title="영문 대문자로 시작하는 2~20자"
                error={errors.code}
                onChange={(e) =>
                  setDraft({ ...draft, code: e.target.value.toUpperCase() })
                }
              />
              <Field
                label="제목"
                value={draft.title}
                required
                maxLength={200}
                error={errors.title}
                onChange={(e) => setDraft({ ...draft, title: e.target.value })}
              />
              <div className="field">
                <label htmlFor="pm-trigger">기준</label>
                <select
                  id="pm-trigger"
                  value={draft.triggerKind}
                  aria-invalid={!!errors.triggerKind}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      triggerKind: e.target.value as TriggerKind,
                    })
                  }
                >
                  {(Object.keys(TRIGGER_LABEL) as TriggerKind[]).map((k) => (
                    <option
                      key={k}
                      value={k}
                      disabled={k !== "CALENDAR" && !fromSource}
                    >
                      {TRIGGER_LABEL[k]}
                    </option>
                  ))}
                </select>
                <small>
                  {fromSource
                    ? "운전 시간·타수는 MES에서 읽습니다. CMMS는 저장하지 않습니다."
                    : "사용량 기준은 MES에서 가져온 설비·금형에만 쓸 수 있습니다."}
                </small>
                {errors.triggerKind && <small>{errors.triggerKind}</small>}
              </div>
              {draft.triggerKind === "CALENDAR" ? (
                <Field
                  label="주기(일)"
                  type="number"
                  min={1}
                  max={365}
                  value={draft.intervalDays}
                  required
                  error={errors.intervalDays}
                  onChange={(e) =>
                    setDraft({ ...draft, intervalDays: e.target.value })
                  }
                />
              ) : (
                <Field
                  label={`주기(${TRIGGER_UNIT[draft.triggerKind]})`}
                  value={draft.intervalUsage}
                  required
                  inputMode="decimal"
                  error={errors.intervalUsage}
                  onChange={(e) =>
                    setDraft({ ...draft, intervalUsage: e.target.value })
                  }
                />
              )}
              <Field
                label="시작일"
                type="date"
                value={draft.startOn}
                required
                onChange={(e) =>
                  setDraft({ ...draft, startOn: e.target.value })
                }
              />
            </FormPanel>
          ) : (
            open && (
              <DetailPanel
                wide
                title={`${open.code} ${open.title}`}
                guard={guard}
                onClose={() => setOpen(null)}
              >
                <PlanDetail
                  key={open.id}
                  plan={open}
                  onChanged={() => list.reload()}
                />
              </DetailPanel>
            )
          )}
        </div>
      )}
    </div>
  );
}
