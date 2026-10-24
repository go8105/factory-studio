// Q-10 공급처 품질 — 검사 수준(F05)·월 평가(F51)·시정 요구(F14) 세 묶음 한 화면.
// 현재 수준은 저장하지 않는다. 등급은 계산 결과이고 수준 전환은 사람이 확정한다.
import { useEffect, useState, type FormEvent } from "react";
import { useSession } from "../app/session";
import { api, ApiError } from "../shared/api";
import {
  DataTable,
  DetailPanel,
  ErrorNotice,
  FormPanel,
  Loading,
  PageTitle,
  useDiscardGuard,
  type Column,
} from "../shared/components";
import {
  fieldErrors,
  GradeBadge,
  LEVEL,
  LevelBadge,
  ModuleOff,
  moduleOff,
  num,
  QMS,
  ScarBadge,
  SCAR_STATUS,
  time,
  useSend,
  type InspectionLevel,
  type Partner,
  type Scar,
  type SupplierLevel,
  type SupplierRating,
} from "./common";

type Tab = "levels" | "ratings" | "scars";
const TABS: Record<Tab, string> = {
  levels: "검사 수준",
  ratings: "월 평가",
  scars: "시정 요구",
};
type LevelDraft = {
  partnerCode: string;
  itemCode: string;
  level: InspectionLevel;
  validFrom: string;
  reason: string;
  ratingId: number | null;
};
const LEVEL_BLANK: LevelDraft = {
  partnerCode: "",
  itemCode: "",
  level: "NORMAL",
  validFrom: "",
  reason: "",
  ratingId: null,
};
type ScarDraft = {
  partnerCode: string;
  dueOn: string;
  ncrId: string;
};
const SCAR_BLANK: ScarDraft = { partnerCode: "", dueOn: "", ncrId: "" };
type Panel =
  | { kind: "level" }
  | { kind: "scar" }
  | { kind: "scarDetail" | "scarRespond"; id: number };

export function Suppliers() {
  const { fail } = useSession();
  const [tab, setTab] = useState<Tab>("levels");
  const [month, setMonth] = useState("");
  const [levels, setLevels] = useState<SupplierLevel[]>();
  const [ratings, setRatings] = useState<SupplierRating[]>();
  const [scars, setScars] = useState<Scar[]>();
  const [partners, setPartners] = useState<Partner[]>([]);
  const [error, setError] = useState<unknown>();
  const [reload, setReload] = useState(0);
  const [panel, setPanel] = useState<Panel | null>(null);
  const [scarDetail, setScarDetail] = useState<Scar>();
  const [level, setLevel] = useState<LevelDraft>(LEVEL_BLANK);
  const [scar, setScar] = useState<ScarDraft>(SCAR_BLANK);
  const [reply, setReply] = useState("");
  const [done, setDone] = useState("");
  const {
    send,
    pending,
    error: saveError,
    setError: setSaveError,
  } = useSend(() => setReload((n) => n + 1));
  const dirty =
    panel?.kind === "level"
      ? JSON.stringify(level) !== JSON.stringify(LEVEL_BLANK)
      : panel?.kind === "scar"
        ? JSON.stringify(scar) !== JSON.stringify(SCAR_BLANK)
        : panel?.kind === "scarRespond"
          ? reply !== ""
          : false;
  const guard = useDiscardGuard(dirty);

  useEffect(() => {
    const controller = new AbortController();
    const query = month ? `?month=${month}` : "";
    Promise.all([
      api<SupplierLevel[]>(`${QMS}/supplier-levels`, {
        signal: controller.signal,
      }),
      api<SupplierRating[]>(`${QMS}/supplier-ratings${query}`, {
        signal: controller.signal,
      }),
      api<Scar[]>(`${QMS}/scars`, { signal: controller.signal }),
    ])
      .then(([l, r, s]) => {
        if (controller.signal.aborted) return;
        setLevels(l.data);
        setRatings(r.data);
        setScars(s.data);
      })
      .catch((e) => {
        if (controller.signal.aborted) return;
        setError(e);
        if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
      });
    return () => controller.abort();
  }, [month, reload]);

  useEffect(() => {
    api<Partner[]>(`${QMS}/suppliers`)
      .then((r) => setPartners(r.data))
      .catch(() => setPartners([]));
  }, []);

  if (moduleOff(error)) return <ModuleOff />;
  const errors = fieldErrors(saveError);

  function openLevel(from?: SupplierRating) {
    setLevel(
      from
        ? {
            ...LEVEL_BLANK,
            partnerCode: from.partnerCode,
            level: from.suggestedLevel ?? "NORMAL",
            reason: `${from.ratingMonth} 평가 ${from.grade}등급 제안`,
            ratingId: from.id,
          }
        : LEVEL_BLANK,
    );
    setSaveError(undefined);
    setPanel({ kind: "level" });
  }
  async function openScar(id: number) {
    setSaveError(undefined);
    const found = (scars ?? []).find((s) => s.id === id);
    setScarDetail(found);
    setPanel({ kind: "scarDetail", id });
  }

  async function submitLevel(event: FormEvent) {
    event.preventDefault();
    const saved = await send<SupplierLevel>("/supplier-levels", "POST", {
      partnerCode: level.partnerCode,
      itemCode: level.itemCode.trim() || null,
      level: level.level,
      validFrom: level.validFrom,
      reason: level.reason,
      ratingId: level.ratingId,
    });
    if (saved) {
      setDone(
        `${saved.partnerCode} 검사 수준을 ${LEVEL[saved.level]}(으)로 정했습니다.`,
      );
      setPanel(null);
      setTab("levels");
    }
  }
  async function calculate() {
    if (!month) return;
    const saved = await send<{ month: string; partners: string[] }>(
      `/supplier-ratings?month=${month}`,
      "POST",
    );
    if (saved)
      setDone(
        saved.partners.length
          ? `${saved.month} 공급처 ${saved.partners.length}곳을 평가했습니다.`
          : `${saved.month}에 확정한 수입 검사가 없어 평가할 공급처가 없습니다.`,
      );
  }
  async function submitScar(event: FormEvent) {
    event.preventDefault();
    const saved = await send<Scar>("/scars", "POST", {
      partnerCode: scar.partnerCode,
      dueOn: scar.dueOn,
      ncrId: scar.ncrId ? Number(scar.ncrId) : null,
    });
    if (saved) {
      setDone(`${saved.scarNo} 시정 요구를 발행했습니다.`);
      setPanel(null);
      setTab("scars");
    }
  }
  async function submitReply(event: FormEvent) {
    event.preventDefault();
    if (!scarDetail) return;
    const saved = await send<Scar>(`/scars/${scarDetail.id}/response`, "POST", {
      response: reply,
    });
    if (saved) {
      setDone(`${saved.scarNo} 회신을 받았습니다.`);
      setScarDetail(saved);
      setPanel({ kind: "scarDetail", id: saved.id });
    }
  }
  async function closeScar() {
    if (!scarDetail) return;
    const saved = await send<Scar>(`/scars/${scarDetail.id}/closure`, "POST");
    if (saved) {
      setDone(`${saved.scarNo} 종결`);
      setScarDetail(saved);
    }
  }

  const levelColumns: Column<SupplierLevel>[] = [
    { key: "partnerCode", label: "공급처" },
    { key: "itemCode", label: "품목", render: (r) => r.itemCode ?? "전체" },
    {
      key: "level",
      label: "수준",
      render: (r) => <LevelBadge level={r.level} />,
    },
    { key: "validFrom", label: "적용일" },
    {
      key: "isCurrent",
      label: "현재",
      render: (r) =>
        r.isCurrent ? "현재" : <span className="muted">이력</span>,
    },
    { key: "reason", label: "사유" },
  ];
  const ratingColumns: Column<SupplierRating>[] = [
    { key: "ratingMonth", label: "월" },
    { key: "partnerCode", label: "공급처" },
    { key: "lotCount", label: "검사 LOT" },
    { key: "failedLotCount", label: "불합격" },
    { key: "defectPpm", label: "불량 PPM", render: (r) => num(r.defectPpm, 1) },
    { key: "scarCount", label: "시정 요구" },
    {
      key: "grade",
      label: "등급",
      render: (r) => <GradeBadge grade={r.grade} />,
    },
    {
      key: "suggestedLevel",
      label: "전환 제안",
      render: (r) =>
        r.suggestedLevel ? (
          <button
            type="button"
            className="link-button"
            onClick={() => guard.guard(() => openLevel(r))}
          >
            {LEVEL[r.suggestedLevel]}로 확정
          </button>
        ) : (
          <span className="muted">없음</span>
        ),
    },
  ];
  const scarColumns: Column<Scar>[] = [
    { key: "scarNo", label: "요구 번호" },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <button
          type="button"
          className="link-button"
          onClick={() => guard.guard(() => void openScar(r.id))}
        >
          상세
        </button>
      ),
    },
    { key: "partnerCode", label: "공급처" },
    { key: "ncrNo", label: "근거 부적합", render: (r) => r.ncrNo ?? "—" },
    { key: "issuedOn", label: "발행일" },
    { key: "dueOn", label: "회신 기한" },
    {
      key: "status",
      label: "상태",
      render: (r) => <ScarBadge status={r.status} />,
    },
  ];

  const ready = levels && ratings && scars;
  return (
    <div className="page-fill">
      <PageTitle
        id="Q-10"
        title="공급처 품질"
        subtitle="검사 수준과 월 평가, 공급처 시정 요구를 관리합니다"
        help="qms/q-10"
      />
      <p className="muted" role="note">
        <strong>현재 검사 수준은 저장하지 않습니다.</strong> 적용일이 오늘
        이하인 가장 최근 행이 현재입니다. 월 평가는 <strong>제안까지만</strong>{" "}
        하고, 수준 전환은 사람이 확정합니다. 시정 요구는 기록이며 메일을 보내지
        않습니다.
      </p>
      {done && <p role="status">{done}</p>}
      <ErrorNotice error={error} retry={() => setReload((n) => n + 1)} />
      {!ready ? (
        !error && <Loading delay={300} />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <div className="filter-bar">
              {(Object.keys(TABS) as Tab[]).map((key) => (
                <button
                  key={key}
                  type="button"
                  className={tab === key ? undefined : "secondary"}
                  aria-pressed={tab === key}
                  onClick={() => setTab(key)}
                >
                  {TABS[key]}
                </button>
              ))}
            </div>
            {tab === "levels" && (
              <>
                <div className="filter-bar">
                  <button
                    type="button"
                    onClick={() => guard.guard(() => openLevel())}
                  >
                    검사 수준 정하기
                  </button>
                </div>
                <DataTable
                  rows={levels}
                  columns={levelColumns}
                  caption="공급처 검사 수준 이력"
                  offset={0}
                  total={levels.length}
                  limit={levels.length || 1}
                  onPage={() => undefined}
                  empty={
                    <p className="muted">
                      정한 검사 수준이 없습니다. 수준을 정하지 않은 공급처는
                      보통으로 봅니다.
                    </p>
                  }
                />
              </>
            )}
            {tab === "ratings" && (
              <>
                <div className="filter-bar">
                  <label>
                    평가 월
                    <input
                      type="month"
                      value={month}
                      onChange={(e) => setMonth(e.target.value)}
                    />
                  </label>
                  <button
                    type="button"
                    disabled={!month || pending}
                    onClick={() => void calculate()}
                  >
                    이 달 평가 계산
                  </button>
                </div>
                <p className="muted">
                  평가는 <strong>확정한 수입 검사</strong>로 계산합니다. 수입
                  검사 화면이 아직 없어 지금은 평가할 대상이 없을 수 있습니다.
                </p>
                <DataTable
                  rows={ratings}
                  columns={ratingColumns}
                  caption="공급처 월 평가"
                  offset={0}
                  total={ratings.length}
                  limit={ratings.length || 1}
                  onPage={() => undefined}
                  empty={
                    <p className="muted">
                      평가 결과가 없습니다. 달을 고르고 계산하세요.
                    </p>
                  }
                />
              </>
            )}
            {tab === "scars" && (
              <>
                <div className="filter-bar">
                  <button
                    type="button"
                    onClick={() =>
                      guard.guard(() => {
                        setScar(SCAR_BLANK);
                        setSaveError(undefined);
                        setPanel({ kind: "scar" });
                      })
                    }
                  >
                    시정 요구 발행
                  </button>
                </div>
                <DataTable
                  rows={scars}
                  columns={scarColumns}
                  caption="공급처 시정 요구"
                  offset={0}
                  total={scars.length}
                  limit={scars.length || 1}
                  onPage={() => undefined}
                  empty={
                    <p className="muted">
                      시정 요구가 없습니다. 공급처 탓인 부적합이 생기면
                      발행합니다.
                    </p>
                  }
                />
              </>
            )}
          </section>

          {panel?.kind === "level" && (
            <FormPanel
              key="level"
              title="검사 수준 정하기"
              guard={guard}
              onClose={() => setPanel(null)}
              onSubmit={(e) => void submitLevel(e)}
              actions={
                <button type="submit" disabled={pending} aria-busy={pending}>
                  저장
                </button>
              }
            >
              <ErrorNotice
                error={Object.keys(errors).length ? undefined : saveError}
              />
              <p className="muted">
                수준은 고치지 않고 <strong>새 행으로 쌓습니다.</strong> 언제부터
                무엇이었는지가 남아야 하기 때문입니다.
              </p>
              <div className="field">
                <label htmlFor="level-partner">공급처</label>
                {partners.length ? (
                  <select
                    id="level-partner"
                    required
                    value={level.partnerCode}
                    aria-invalid={!!errors.partnerCode}
                    onChange={(e) =>
                      setLevel({ ...level, partnerCode: e.target.value })
                    }
                  >
                    <option value="">선택</option>
                    {partners.map((p) => (
                      <option key={p.partnerCode} value={p.partnerCode}>
                        {p.partnerCode} {p.partnerName}
                      </option>
                    ))}
                  </select>
                ) : (
                  <>
                    <input
                      id="level-partner"
                      required
                      maxLength={40}
                      value={level.partnerCode}
                      aria-invalid={!!errors.partnerCode}
                      onChange={(e) =>
                        setLevel({
                          ...level,
                          partnerCode: e.target.value.toUpperCase(),
                        })
                      }
                    />
                    <small>ERP를 사용하지 않아 코드를 직접 적습니다.</small>
                  </>
                )}
                {errors.partnerCode && <small>{errors.partnerCode}</small>}
              </div>
              <div className="field">
                <label htmlFor="level-item">품목 코드 (선택)</label>
                <input
                  id="level-item"
                  maxLength={40}
                  value={level.itemCode}
                  onChange={(e) =>
                    setLevel({
                      ...level,
                      itemCode: e.target.value.toUpperCase(),
                    })
                  }
                />
                <small>비우면 그 공급처 전체에 적용합니다.</small>
              </div>
              <div className="field">
                <label htmlFor="level-level">검사 수준</label>
                <select
                  id="level-level"
                  value={level.level}
                  onChange={(e) =>
                    setLevel({
                      ...level,
                      level: e.target.value as InspectionLevel,
                    })
                  }
                >
                  {(Object.keys(LEVEL) as InspectionLevel[]).map((l) => (
                    <option key={l} value={l}>
                      {LEVEL[l]}
                    </option>
                  ))}
                </select>
                <small>
                  면제는 수입 검사를 하지 않고, 강화는 더 촘촘히 뽑습니다.
                </small>
              </div>
              <div className="field">
                <label htmlFor="level-from">적용일</label>
                <input
                  id="level-from"
                  type="date"
                  required
                  value={level.validFrom}
                  aria-invalid={!!errors.validFrom}
                  onChange={(e) =>
                    setLevel({ ...level, validFrom: e.target.value })
                  }
                />
                {errors.validFrom && <small>{errors.validFrom}</small>}
              </div>
              <div className="field">
                <label htmlFor="level-reason">사유</label>
                <textarea
                  id="level-reason"
                  required
                  minLength={2}
                  maxLength={300}
                  rows={3}
                  value={level.reason}
                  aria-invalid={!!errors.reason}
                  onChange={(e) =>
                    setLevel({ ...level, reason: e.target.value })
                  }
                />
                {errors.reason && <small>{errors.reason}</small>}
              </div>
            </FormPanel>
          )}

          {panel?.kind === "scar" && (
            <FormPanel
              key="scar"
              title="시정 요구 발행"
              guard={guard}
              onClose={() => setPanel(null)}
              onSubmit={(e) => void submitScar(e)}
              actions={
                <button type="submit" disabled={pending} aria-busy={pending}>
                  발행
                </button>
              }
            >
              <ErrorNotice
                error={Object.keys(errors).length ? undefined : saveError}
              />
              <p className="muted">
                발행은 <strong>기록만 남깁니다.</strong> 공급처에 메일이나
                팩스를 보내지 않습니다.
              </p>
              <div className="field">
                <label htmlFor="scar-partner">공급처</label>
                {partners.length ? (
                  <select
                    id="scar-partner"
                    required
                    value={scar.partnerCode}
                    aria-invalid={!!errors.partnerCode}
                    onChange={(e) =>
                      setScar({ ...scar, partnerCode: e.target.value })
                    }
                  >
                    <option value="">선택</option>
                    {partners.map((p) => (
                      <option key={p.partnerCode} value={p.partnerCode}>
                        {p.partnerCode} {p.partnerName}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    id="scar-partner"
                    required
                    maxLength={40}
                    value={scar.partnerCode}
                    aria-invalid={!!errors.partnerCode}
                    onChange={(e) =>
                      setScar({
                        ...scar,
                        partnerCode: e.target.value.toUpperCase(),
                      })
                    }
                  />
                )}
                {errors.partnerCode && <small>{errors.partnerCode}</small>}
              </div>
              <div className="field">
                <label htmlFor="scar-ncr">근거 부적합 보고 번호 (선택)</label>
                <input
                  id="scar-ncr"
                  inputMode="numeric"
                  value={scar.ncrId}
                  aria-invalid={!!errors.ncrId}
                  onChange={(e) => setScar({ ...scar, ncrId: e.target.value })}
                />
                <small>부적합 보고 화면의 번호(id)를 적습니다.</small>
                {errors.ncrId && <small>{errors.ncrId}</small>}
              </div>
              <div className="field">
                <label htmlFor="scar-due">회신 기한</label>
                <input
                  id="scar-due"
                  type="date"
                  required
                  value={scar.dueOn}
                  aria-invalid={!!errors.dueOn}
                  onChange={(e) => setScar({ ...scar, dueOn: e.target.value })}
                />
                {errors.dueOn && <small>{errors.dueOn}</small>}
              </div>
            </FormPanel>
          )}

          {panel?.kind === "scarDetail" && scarDetail && (
            <DetailPanel
              key={`scar-${scarDetail.id}`}
              title={`${scarDetail.scarNo} · ${scarDetail.partnerCode}`}
              onClose={() => setPanel(null)}
              actions={
                <>
                  {scarDetail.status === "OPEN" && (
                    <button
                      type="button"
                      onClick={() => {
                        setReply("");
                        setSaveError(undefined);
                        setPanel({ kind: "scarRespond", id: scarDetail.id });
                      }}
                    >
                      회신 입력
                    </button>
                  )}
                  {scarDetail.status === "RESPONDED" && (
                    <button
                      type="button"
                      className="secondary"
                      disabled={pending}
                      onClick={() => void closeScar()}
                    >
                      종결
                    </button>
                  )}
                </>
              }
            >
              <ErrorNotice error={saveError} />
              <p>
                <ScarBadge status={scarDetail.status} /> 발행{" "}
                {scarDetail.issuedOn} · 회신 기한 {scarDetail.dueOn}
                {scarDetail.closedAt && ` · 종결 ${time(scarDetail.closedAt)}`}
              </p>
              <p className="muted">
                근거: {scarDetail.ncrNo ?? scarDetail.inspectionNo ?? "없음"}
              </p>
              {scarDetail.response ? (
                <>
                  <h3>공급처 회신 ({scarDetail.respondedOn})</h3>
                  <p className="wrap">{scarDetail.response}</p>
                </>
              ) : (
                <p className="muted">아직 회신을 받지 않았습니다.</p>
              )}
            </DetailPanel>
          )}

          {panel?.kind === "scarRespond" && scarDetail && (
            <FormPanel
              key={`reply-${scarDetail.id}`}
              title={`${scarDetail.scarNo} 회신 입력`}
              guard={guard}
              onClose={() =>
                setPanel({ kind: "scarDetail", id: scarDetail.id })
              }
              onSubmit={(e) => void submitReply(e)}
              actions={
                <>
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    저장
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() =>
                      guard.guard(() =>
                        setPanel({ kind: "scarDetail", id: scarDetail.id }),
                      )
                    }
                  >
                    요구 상세로
                  </button>
                </>
              }
            >
              <ErrorNotice
                error={Object.keys(errors).length ? undefined : saveError}
              />
              <p className="muted">
                공급처가 보내온 내용을 옮겨 적습니다. {SCAR_STATUS.RESPONDED}{" "}
                상태가 되고, 확인되면 종결합니다.
              </p>
              <div className="field">
                <label htmlFor="scar-reply">공급처 회신</label>
                <textarea
                  id="scar-reply"
                  required
                  minLength={2}
                  maxLength={1000}
                  rows={4}
                  value={reply}
                  aria-invalid={!!errors.response}
                  onChange={(e) => setReply(e.target.value)}
                />
                {errors.response && <small>{errors.response}</small>}
              </div>
            </FormPanel>
          )}
        </div>
      )}
    </div>
  );
}
