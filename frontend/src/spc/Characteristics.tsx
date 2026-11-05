// S-07 관리 특성·한계 — 특성 목록 → 상세(한계 버전·게시 TX-S2) · 등록·수정 FormPanel (UI-03 P 패턴, F-12 기준).
import { useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
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
import { api, ApiError } from "../shared/api";
import {
  fieldErrors,
  ModuleOff,
  moduleOff,
  num,
  rulesOf,
  spec,
  SPC,
  time,
  toIso,
  toLocal,
  useGet,
  useSend,
  CHART_TYPE_LABEL,
  DEFAULT_RULES,
  RULE_LABEL,
  type Characteristic,
  type ChartType,
  type Limit,
  type RuleNo,
} from "./common";

type Item = { itemCode: string; name: string };
type Draft = {
  code: string;
  itemCode: string;
  processCode: string;
  name: string;
  unit: string;
  lsl: string;
  usl: string;
  target: string;
  decimals: string;
  isActive: boolean;
  chartType: ChartType;
  subgroupSize: string;
  rules: RuleNo[];
};
type Preview = {
  basisCount: number;
  minimum: number;
  xbarCl?: string;
  xbarUcl?: string;
  xbarLcl?: string;
  rCl?: string;
  rUcl?: string;
};

const blank: Draft = {
  code: "",
  itemCode: "",
  processCode: "",
  name: "",
  unit: "mm",
  lsl: "",
  usl: "",
  target: "",
  decimals: "3",
  isActive: true,
  chartType: "XBAR_R",
  subgroupSize: "5",
  rules: DEFAULT_RULES,
};
const orNull = (v: string) => (v.trim() === "" ? null : v.trim());

function LimitsPanel({
  characteristic: c,
  onDone,
}: {
  characteristic: Characteristic;
  onDone: () => void;
}) {
  const limits = useGet<Limit[]>(`/characteristics/${c.id}/limits`);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState(toLocal(new Date().toISOString()));
  const [reason, setReason] = useState("");
  const [preview, setPreview] = useState<Preview>();
  const [previewError, setPreviewError] = useState<unknown>();
  const { send, pending, error } = useSend(() => {
    limits.reload();
    onDone();
  });
  const errors = fieldErrors(error);
  useEffect(() => setPreview(undefined), [from, to]);
  async function check() {
    setPreviewError(undefined);
    try {
      const q = new URLSearchParams({
        basisFrom: toIso(from),
        basisTo: toIso(to),
      });
      const r = await api<Preview>(
        `${SPC}/characteristics/${c.id}/limits/preview?${q}`,
      );
      setPreview(r.data);
    } catch (e) {
      setPreviewError(e);
    }
  }
  async function publish(event: FormEvent) {
    event.preventDefault();
    const r = await send("/characteristics/" + c.id + "/limits", "POST", {
      basisFrom: toIso(from),
      basisTo: toIso(to),
      reason,
    });
    if (r) {
      setReason("");
      setPreview(undefined);
    }
  }
  const digits = c.decimals + 1;
  const columns: Column<Limit>[] = [
    { key: "version", label: "버전", render: (l) => `v${l.version}` },
    { key: "publishedAt", label: "게시", render: (l) => time(l.publishedAt) },
    {
      key: "effectiveAt",
      label: "적용",
      render: (l) => `${time(l.effectiveAt)} 이후 측정분`,
    },
    {
      key: "basisFrom",
      label: "기준 구간",
      render: (l) =>
        `${time(l.basisFrom)} ~ ${time(l.basisTo)} · ${l.basisCount}개`,
    },
    {
      key: "xbarCl",
      label: "X̄ LCL · CL · UCL",
      render: (l) =>
        `${num(l.xbarLcl, digits)} · ${num(l.xbarCl, digits)} · ${num(l.xbarUcl, digits)}`,
    },
    {
      key: "rCl",
      label: "R CL · UCL",
      render: (l) => `${num(l.rCl, digits)} · ${num(l.rUcl, digits)}`,
    },
    { key: "reason", label: "사유" },
  ];
  const short = preview && preview.basisCount < preview.minimum;
  return (
    <>
      <ErrorNotice error={limits.error} />
      {!limits.data ? (
        <Loading />
      ) : (
        <DataTable
          rows={limits.data}
          columns={columns}
          caption="관리 한계 버전"
          offset={0}
          total={limits.data.length}
          limit={limits.data.length || 1}
          onPage={() => undefined}
          empty={<p className="muted">게시한 한계가 없습니다.</p>}
        />
      )}
      <form className="spc-publish" onSubmit={(e) => void publish(e)}>
        <h3>한계 게시</h3>
        <p className="muted">
          기준 구간의 유효 부분군 20개 이상으로 계산합니다. 게시한 한계는 바꾸지
          않고, 다시 계산하면 새 버전이 됩니다. 새 버전은 게시할 때의 마지막
          부분군보다 늦게 측정한 부분군부터 적용합니다.
        </p>
        <div className="field">
          <label htmlFor="spc-basis-from">기준 구간 시작</label>
          <input
            id="spc-basis-from"
            type="datetime-local"
            value={from}
            required
            onChange={(e) => setFrom(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="spc-basis-to">기준 구간 종료</label>
          <input
            id="spc-basis-to"
            type="datetime-local"
            value={to}
            required
            aria-invalid={!!errors.basisTo}
            onChange={(e) => setTo(e.target.value)}
          />
          {(errors.basisTo || errors.basisFrom) && (
            <small>{errors.basisTo ?? errors.basisFrom}</small>
          )}
        </div>
        <button
          type="button"
          className="secondary"
          disabled={!from || !to}
          onClick={() => void check()}
        >
          미리 계산
        </button>
        <ErrorNotice error={previewError} />
        {preview && (
          <p role="status">
            유효 부분군 {preview.basisCount}개
            {short
              ? ` — ${preview.minimum}개 이상 필요`
              : ` · X̄ ${num(preview.xbarLcl, digits)} ~ ${num(preview.xbarUcl, digits)} (CL ${num(preview.xbarCl, digits)}) · R UCL ${num(preview.rUcl, digits)}`}
          </p>
        )}
        <Field
          label="게시 사유"
          value={reason}
          required
          minLength={2}
          maxLength={200}
          error={errors.reason}
          onChange={(e) => setReason(e.target.value)}
        />
        <ErrorNotice
          error={
            Object.keys(errors).length
              ? undefined
              : error instanceof ApiError
                ? error
                : undefined
          }
        />
        <button
          type="submit"
          disabled={pending || !preview || short}
          aria-busy={pending}
          title={!preview ? "먼저 미리 계산하세요." : undefined}
        >
          게시
        </button>
      </form>
    </>
  );
}

export function Characteristics() {
  const [params] = useSearchParams();
  const list = useGet<Characteristic[]>("/characteristics");
  const items = useGet<Item[]>("/lookups/items");
  const [openId, setOpenId] = useState<number | null>(
    Number(params.get("c")) || null,
  );
  const [edit, setEdit] = useState<Characteristic | "new" | null>(null);
  const [draft, setDraft] = useState<Draft>(blank);
  const [initial, setInitial] = useState<Draft>(blank);
  const { send, pending, error, setError } = useSend(() => list.reload());
  const guard = useDiscardGuard(
    !!edit && JSON.stringify(draft) !== JSON.stringify(initial),
  );
  if (moduleOff(list.error)) return <ModuleOff />;
  const errors = fieldErrors(error);
  const open = list.data?.find((c) => c.id === openId) ?? null;
  const inUse = edit !== null && edit !== "new" && edit.subgroupCount > 0;

  function start(target: Characteristic | "new") {
    const values: Draft =
      target === "new"
        ? { ...blank, itemCode: items.data?.[0]?.itemCode ?? "" }
        : {
            code: target.code,
            itemCode: target.itemCode,
            processCode: target.processCode,
            name: target.name,
            unit: target.unit,
            lsl: target.lsl ?? "",
            usl: target.usl ?? "",
            target: target.target ?? "",
            decimals: String(target.decimals),
            isActive: target.isActive,
            chartType: target.chartType,
            subgroupSize: String(target.subgroupSize),
            rules: rulesOf(target),
          };
    guard.guard(() => {
      setEdit(target);
      setDraft(values);
      setInitial(values);
      setError(undefined);
    });
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!edit) return;
    const specFields = {
      unit: draft.unit,
      lsl: orNull(draft.lsl),
      usl: orNull(draft.usl),
      target: orNull(draft.target),
      chartType: draft.chartType,
      subgroupSize: Number(draft.subgroupSize),
    };
    // 규칙은 부분군이 있어도 바꿀 수 있다 — 지난 판정은 그대로 두고 다음 부분군부터 적용된다.
    const rules = [...draft.rules].sort((a, b) => a - b);
    const saved =
      edit === "new"
        ? await send("/characteristics", "POST", {
            code: draft.code,
            itemCode: draft.itemCode,
            processCode: draft.processCode,
            name: draft.name,
            decimals: Number(draft.decimals),
            rules,
            ...specFields,
          })
        : await send(`/characteristics/${edit.id}`, "PATCH", {
            name: draft.name,
            decimals: Number(draft.decimals),
            isActive: draft.isActive,
            rules,
            ...(inUse ? {} : specFields),
          });
    if (saved) setEdit(null);
  }
  const columns: Column<Characteristic>[] = [
    { key: "code", label: "코드" },
    {
      key: "id",
      label: "관리",
      render: (c) => (
        <>
          <button
            type="button"
            className="link-button"
            aria-pressed={openId === c.id}
            onClick={() => guard.guard(() => setOpenId(c.id))}
          >
            한계
          </button>{" "}
          <button
            type="button"
            className="link-button"
            onClick={() => start(c)}
          >
            수정
          </button>
        </>
      ),
    },
    { key: "itemCode", label: "품목" },
    { key: "processCode", label: "공정" },
    { key: "name", label: "특성명" },
    { key: "lsl", label: "규격", render: (c) => spec(c) },
    {
      key: "chartType",
      label: "관리도",
      render: (c) =>
        c.chartType === "I_MR" ? "I-MR" : `X̄-R (n=${c.subgroupSize})`,
    },
    {
      key: "rules",
      label: "판정 규칙",
      render: (c) => rulesOf(c).join("·"),
    },
    {
      key: "limitVersion",
      label: "한계",
      render: (c) =>
        c.limitVersion ? (
          `v${c.limitVersion}`
        ) : (
          <Badge tone="warning">미게시</Badge>
        ),
    },
    { key: "subgroupCount", label: "부분군" },
    {
      key: "isActive",
      label: "사용",
      render: (c) =>
        c.isActive ? (
          <Badge>사용</Badge>
        ) : (
          <Badge tone="warning">사용 안 함</Badge>
        ),
    },
  ];
  const itemsOff =
    items.error instanceof ApiError &&
    items.error.error.details?.reason === "SOURCE_MODULE_DISABLED";
  return (
    <div className="page-fill">
      <PageTitle
        id="S-07"
        title="관리 특성·한계"
        subtitle="관리할 품목·공정·특성과 규격, 관리 한계 버전"
        help="spc/s-07"
        actions={
          <button
            type="button"
            aria-pressed={edit === "new"}
            disabled={itemsOff}
            title={
              itemsOff
                ? "MES를 사용하지 않도록 설정해 품목을 고를 수 없습니다."
                : undefined
            }
            onClick={() => start("new")}
          >
            특성 등록
          </button>
        }
      />
      <ErrorNotice error={list.error} retry={() => list.reload()} />
      {itemsOff && (
        <p role="note" className="muted">
          MES를 사용하지 않도록 설정해 새 특성은 등록할 수 없습니다. 기존 특성의
          한계 게시·수정은 그대로 쓸 수 있습니다.
        </p>
      )}
      {!list.data ? (
        !list.error && <Loading />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <DataTable
              rows={list.data}
              columns={columns}
              caption="관리 특성"
              offset={0}
              total={list.data.length}
              limit={list.data.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="관리 특성이 없습니다."
                  action="특성 등록"
                  onAction={() => start("new")}
                />
              }
            />
          </section>
          {edit ? (
            <FormPanel
              key={edit === "new" ? "new" : edit.id}
              title={edit === "new" ? "관리 특성 등록" : "관리 특성 수정"}
              guard={guard}
              onClose={() => setEdit(null)}
              onSubmit={(e) => void submit(e)}
              actions={
                <>
                  <button type="submit" disabled={pending} aria-busy={pending}>
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
              {inUse && (
                <p role="note" className="muted">
                  부분군이 있어 규격·단위·품목·공정·관리도 종류는 바꿀 수
                  없습니다. 바꾸려면 새 특성을 등록하세요. 판정 규칙은 바꿀 수
                  있고 다음 부분군부터 적용됩니다.
                </p>
              )}
              <Field
                label="특성 코드"
                value={draft.code}
                required
                disabled={edit !== "new"}
                pattern="[A-Z][A-Z0-9\-]{1,19}"
                error={errors.code}
                onChange={(e) =>
                  setDraft({ ...draft, code: e.target.value.toUpperCase() })
                }
              />
              <div className="field">
                <label htmlFor="spc-item">품목(MES 완제품)</label>
                <select
                  id="spc-item"
                  value={draft.itemCode}
                  disabled={edit !== "new"}
                  aria-invalid={!!errors.itemCode}
                  onChange={(e) =>
                    setDraft({ ...draft, itemCode: e.target.value })
                  }
                >
                  {edit !== "new" && (
                    <option value={draft.itemCode}>{draft.itemCode}</option>
                  )}
                  {items.data?.map((i) => (
                    <option key={i.itemCode} value={i.itemCode}>
                      {i.itemCode} {i.name}
                    </option>
                  ))}
                </select>
                {errors.itemCode && <small>{errors.itemCode}</small>}
              </div>
              <Field
                label="공정 코드(MES)"
                value={draft.processCode}
                required
                disabled={edit !== "new"}
                list="spc-processes"
                error={errors.processCode}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    processCode: e.target.value.toUpperCase(),
                  })
                }
              />
              <datalist id="spc-processes">
                <option value="INJ">사출</option>
                <option value="ASM">조립</option>
                <option value="INS">검사</option>
              </datalist>
              <Field
                label="특성명"
                value={draft.name}
                required
                maxLength={100}
                error={errors.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
              />
              <Field
                label="단위"
                value={draft.unit}
                required
                maxLength={10}
                disabled={inUse}
                onChange={(e) => setDraft({ ...draft, unit: e.target.value })}
              />
              {(["lsl", "usl", "target"] as const).map((k) => (
                <Field
                  key={k}
                  label={
                    k === "lsl"
                      ? "규격 하한(LSL)"
                      : k === "usl"
                        ? "규격 상한(USL)"
                        : "목표값(선택)"
                  }
                  value={draft[k]}
                  inputMode="decimal"
                  pattern="-?\d{1,8}(\.\d{1,4})?"
                  disabled={inUse}
                  error={errors[k]}
                  onChange={(e) => setDraft({ ...draft, [k]: e.target.value })}
                />
              ))}
              <div className="field">
                <label htmlFor="spc-chart">관리도 종류</label>
                <select
                  id="spc-chart"
                  value={draft.chartType}
                  disabled={inUse}
                  onChange={(e) => {
                    const chartType = e.target.value as ChartType;
                    setDraft({
                      ...draft,
                      chartType,
                      subgroupSize:
                        chartType === "I_MR"
                          ? "1"
                          : draft.subgroupSize === "1"
                            ? "5"
                            : draft.subgroupSize,
                    });
                  }}
                >
                  {(Object.keys(CHART_TYPE_LABEL) as ChartType[]).map((k) => (
                    <option key={k} value={k}>
                      {CHART_TYPE_LABEL[k]}
                    </option>
                  ))}
                </select>
              </div>
              {draft.chartType === "XBAR_R" && (
                <Field
                  label="부분군 크기(2~10)"
                  type="number"
                  min={2}
                  max={10}
                  value={draft.subgroupSize}
                  disabled={inUse}
                  error={errors.subgroupSize}
                  onChange={(e) =>
                    setDraft({ ...draft, subgroupSize: e.target.value })
                  }
                />
              )}
              <fieldset className="field">
                <legend>판정 규칙(Nelson)</legend>
                {(Object.keys(RULE_LABEL) as unknown as RuleNo[])
                  .map(Number)
                  .map((n) => n as RuleNo)
                  .map((n) => (
                    <label key={n} className="inline-check">
                      <input
                        type="checkbox"
                        checked={draft.rules.includes(n)}
                        disabled={n === 1}
                        onChange={(e) =>
                          setDraft({
                            ...draft,
                            rules: e.target.checked
                              ? [...draft.rules, n]
                              : draft.rules.filter((r) => r !== n),
                          })
                        }
                      />
                      {RULE_LABEL[n]}
                    </label>
                  ))}
                {errors.rules && <small>{errors.rules}</small>}
              </fieldset>
              <Field
                label="표시 소수 자릿수(0~4)"
                type="number"
                min={0}
                max={4}
                value={draft.decimals}
                onChange={(e) =>
                  setDraft({ ...draft, decimals: e.target.value })
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
          ) : (
            open && (
              <DetailPanel
                wide
                title={`${open.itemCode} · ${open.processCode} · ${open.name}`}
                guard={guard}
                onClose={() => setOpenId(null)}
              >
                <p className="muted">
                  {open.code} · 규격 {spec(open)}
                  {open.target && ` · 목표 ${Number(open.target)}`} ·{" "}
                  {open.chartType === "I_MR"
                    ? "I-MR"
                    : `X̄-R (n=${open.subgroupSize})`}{" "}
                  · 규칙 {rulesOf(open).join("·")} · 부분군 {open.subgroupCount}
                  개
                </p>
                <LimitsPanel
                  key={open.id}
                  characteristic={open}
                  onDone={() => list.reload()}
                />
              </DetailPanel>
            )
          )}
        </div>
      )}
    </div>
  );
}
