// F-19 절감 활동 — 계획 → 시행 → 검증 (DSN-15 F32·Q5)
// 검증은 시행 전·후 같은 길이를 견주고, 검증한 과제는 바꾸지 않는다.
import { useState } from "react";
import {
  Badge,
  ErrorNotice,
  Field,
  Loading,
  PageTitle,
} from "../shared/components";
import { fieldErrors, useApiLists, useApiSend } from "../shared/hooks";

type Status = "PLANNED" | "ACTIVE" | "VERIFIED" | "CANCELLED";
const STATUS_LABEL: Record<Status, string> = {
  PLANNED: "계획",
  ACTIVE: "시행 중",
  VERIFIED: "검증 완료",
  CANCELLED: "취소",
};
type Saving = {
  id: number;
  code: string;
  title: string;
  equipmentId: number | null;
  energySourceId: number;
  expectedSaving: string;
  investment: string;
  startOn: string;
  baselineStartOn: string;
  baselineEndOn: string;
  measuredSaving: string | null;
  status: Status;
};
type Evidence = {
  days: number;
  productionAdjusted: boolean;
  periodSaving: string;
  baseline: {
    from: string;
    to: string;
    energy: string;
    production: string | null;
  };
  after: {
    from: string;
    to: string;
    energy: string;
    production: string | null;
  };
};
type Source = {
  id: number;
  sourceCode: string;
  name: string;
  measureUnit: string;
};
type Equipment = { id: number; equipmentCode: string; name: string };

const EMPTY = {
  code: "",
  title: "",
  energySourceId: "",
  equipmentId: "",
  expectedSaving: "",
  investment: "0",
  baselineStartOn: "",
  baselineEndOn: "",
  startOn: "",
};
const num = (v: string, digits = 1) =>
  Number(v).toLocaleString("ko-KR", { maximumFractionDigits: digits });

export function Savings() {
  const lists = useApiLists<[Saving[], Source[], Equipment[]]>("/api/v1/fems", [
    "/savings",
    "/energy-sources",
    "/equipments",
  ]);
  const { send, pending, error } = useApiSend("/api/v1/fems", lists.reload);
  const [draft, setDraft] = useState(EMPTY);
  const [adding, setAdding] = useState(false);
  const [done, setDone] = useState<string>();
  const [evidence, setEvidence] = useState<{ code: string; ev: Evidence }>();

  const [savings, sources, equipments] = lists.data ?? [];
  const errors = fieldErrors(error);
  const unit = (id: number) =>
    sources?.find((s) => s.id === id)?.measureUnit ?? "";

  async function create() {
    const saved = await send<Saving>("/savings", "POST", {
      code: draft.code.trim().toUpperCase(),
      title: draft.title.trim(),
      energySourceId: Number(draft.energySourceId),
      equipmentId: draft.equipmentId ? Number(draft.equipmentId) : null,
      expectedSaving: draft.expectedSaving.trim(),
      investment: draft.investment.trim() || "0",
      baselineStartOn: draft.baselineStartOn,
      baselineEndOn: draft.baselineEndOn,
      startOn: draft.startOn,
    });
    if (saved?.code) {
      setDraft(EMPTY);
      setAdding(false);
      setDone(`${saved.code} 과제를 계획으로 등록했습니다.`);
    }
  }
  async function verify(row: Saving) {
    const r = await send<Saving & { evidence: Evidence }>(
      `/savings/${row.id}/verify`,
      "POST",
    );
    if (r?.evidence) {
      setEvidence({ code: row.code, ev: r.evidence });
      setDone(`${row.code}을(를) 검증했습니다.`);
    }
  }

  return (
    <>
      <PageTitle
        id="F-19"
        title="절감 활동"
        subtitle="개선 과제를 시행하고, 시행 전·후를 견줘 실제 절감을 검증합니다"
        help="fems/f-19"
        actions={
          <button
            type="button"
            aria-pressed={adding}
            onClick={() => setAdding((v) => !v)}
          >
            과제 등록
          </button>
        }
      />
      <ErrorNotice error={Object.keys(errors).length ? undefined : error} />
      {done && <p role="status">{done}</p>}
      {adding && (
        <div className="section-block">
          <div className="field-row">
            <Field
              label="과제 코드"
              value={draft.code}
              required
              error={errors.code}
              onChange={(e) => setDraft({ ...draft, code: e.target.value })}
            />
            <Field
              label="과제명"
              value={draft.title}
              required
              error={errors.title}
              onChange={(e) => setDraft({ ...draft, title: e.target.value })}
            />
            <label>
              에너지원
              <select
                value={draft.energySourceId}
                onChange={(e) =>
                  setDraft({ ...draft, energySourceId: e.target.value })
                }
              >
                <option value="">선택</option>
                {(sources ?? []).map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.sourceCode} {s.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              설비
              <select
                value={draft.equipmentId}
                onChange={(e) =>
                  setDraft({ ...draft, equipmentId: e.target.value })
                }
              >
                <option value="">사업장 공용</option>
                {(equipments ?? []).map((q) => (
                  <option key={q.id} value={q.id}>
                    {q.equipmentCode} {q.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="field-row">
            <Field
              label="예상 절감 (연)"
              inputMode="decimal"
              value={draft.expectedSaving}
              required
              error={errors.expectedSaving}
              onChange={(e) =>
                setDraft({ ...draft, expectedSaving: e.target.value })
              }
            />
            <Field
              label="투자비 (원)"
              inputMode="decimal"
              value={draft.investment}
              onChange={(e) =>
                setDraft({ ...draft, investment: e.target.value })
              }
            />
            <Field
              label="비교 전 시작"
              type="date"
              value={draft.baselineStartOn}
              required
              onChange={(e) =>
                setDraft({ ...draft, baselineStartOn: e.target.value })
              }
            />
            <Field
              label="비교 전 끝(미포함)"
              type="date"
              value={draft.baselineEndOn}
              required
              error={errors.baselineEndOn}
              onChange={(e) =>
                setDraft({ ...draft, baselineEndOn: e.target.value })
              }
            />
            <Field
              label="시행일"
              type="date"
              value={draft.startOn}
              required
              onChange={(e) => setDraft({ ...draft, startOn: e.target.value })}
            />
            <button
              type="button"
              disabled={
                pending ||
                !draft.code.trim() ||
                !draft.energySourceId ||
                !draft.expectedSaving.trim() ||
                !draft.baselineStartOn ||
                !draft.baselineEndOn ||
                !draft.startOn
              }
              onClick={() => void create()}
            >
              등록
            </button>
          </div>
          <p className="muted" role="note">
            비교 후 기간은 <strong>시행일부터 비교 전과 같은 길이</strong>
            입니다. 비교 전은 시행일 앞에서 끝나야 합니다. 설비를 고르지 않으면
            사업장 전체 사용량을 견주고, 이때는{" "}
            <strong>생산량으로 보정하지 않습니다.</strong>
          </p>
        </div>
      )}
      {evidence && (
        <section className="panel" aria-label="검증 근거">
          <h2>
            {evidence.code} 검증 근거 · {evidence.ev.days}일 비교
          </h2>
          <div className="table-scroll">
            <table aria-label="검증 근거">
              <thead>
                <tr>
                  <th scope="col">구간</th>
                  <th scope="col">기간</th>
                  <th scope="col" className="num">
                    사용량
                  </th>
                  <th scope="col" className="num">
                    생산량
                  </th>
                </tr>
              </thead>
              <tbody>
                {(
                  [
                    ["비교 전", evidence.ev.baseline],
                    ["비교 후", evidence.ev.after],
                  ] as const
                ).map(([label, row]) => (
                  <tr key={label}>
                    <th scope="row">{label}</th>
                    <td>
                      {row.from} ~ {row.to}
                    </td>
                    <td className="num">{num(row.energy)}</td>
                    <td className="num">
                      {row.production ? num(row.production) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted">
            기간 절감 {num(evidence.ev.periodSaving)}
            {evidence.ev.productionAdjusted
              ? " · 생산량으로 보정한 값입니다."
              : " · 설비가 없어 생산량으로 보정하지 않은 사용량 차이입니다."}
          </p>
        </section>
      )}
      {!savings ? (
        !lists.error && <Loading delay={300} />
      ) : savings.length === 0 ? (
        <p className="muted">
          등록한 절감 과제가 없습니다. 과제 등록으로 시작하세요.
        </p>
      ) : (
        <div className="table-scroll">
          <table aria-label="절감 과제">
            <thead>
              <tr>
                <th scope="col">과제</th>
                <th scope="col">상태</th>
                <th scope="col">시행일</th>
                <th scope="col" className="num">
                  예상 절감(연)
                </th>
                <th scope="col" className="num">
                  실제 절감(연)
                </th>
                <th scope="col">관리</th>
              </tr>
            </thead>
            <tbody>
              {savings.map((s) => (
                <tr key={s.id}>
                  <td>
                    {s.code} {s.title}
                  </td>
                  <td>
                    <Badge tone={s.status === "ACTIVE" ? "warning" : "normal"}>
                      {STATUS_LABEL[s.status]}
                    </Badge>
                  </td>
                  <td>{s.startOn}</td>
                  <td className="num">
                    {num(s.expectedSaving, 0)} {unit(s.energySourceId)}
                  </td>
                  <td className="num">
                    {s.measuredSaving === null
                      ? "—"
                      : `${num(s.measuredSaving, 0)} ${unit(s.energySourceId)}`}
                  </td>
                  <td>
                    <span className="row-actions">
                      {s.status === "PLANNED" && (
                        <button
                          type="button"
                          className="link-button"
                          disabled={pending}
                          onClick={() =>
                            void send(`/savings/${s.id}/start`, "POST")
                          }
                        >
                          시행 시작
                        </button>
                      )}
                      {s.status === "ACTIVE" && (
                        <button
                          type="button"
                          className="link-button"
                          disabled={pending}
                          onClick={() => void verify(s)}
                        >
                          검증
                        </button>
                      )}
                      {(s.status === "PLANNED" || s.status === "ACTIVE") && (
                        <button
                          type="button"
                          className="link-button"
                          disabled={pending}
                          onClick={() =>
                            void send(`/savings/${s.id}/cancel`, "POST")
                          }
                        >
                          취소
                        </button>
                      )}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
