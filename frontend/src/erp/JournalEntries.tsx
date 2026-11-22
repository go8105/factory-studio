// E-30 전표 입력·조회 (DSN-11 F42~F45·F47)
import { useState } from "react";
import {
  Badge,
  DataTable,
  ErrorNotice,
  Field,
  Loading,
  PageTitle,
} from "../shared/components";
import {
  fieldErrors,
  ModuleOff,
  moduleOff,
  useLists,
  useSend,
  won,
  type Partner,
} from "./common";

type Line = {
  id: number;
  lineNo: number;
  accountId: number;
  accountCode: string;
  accountName: string;
  side: "DEBIT" | "CREDIT";
  amount: string;
  partnerCode: string | null;
  departmentCode: string | null;
  memo: string | null;
};
type Entry = {
  id: number;
  entryNo: string;
  entryDate: string;
  entryKind: string;
  status: "draft" | "confirmed" | "reversed";
  description: string | null;
  sourceKind: string | null;
  sourceRef: string | null;
  reversalOfNo: string | null;
  reversedByNo: string | null;
  debitTotal: string;
  creditTotal: string;
  lines: Line[];
};
type Account = {
  id: number;
  accountCode: string;
  accountName: string;
  requiresPartner: boolean;
  requiresDepartment: boolean;
  isActive: boolean;
};
type Dept = { id: number; code: string; name: string };
type DraftLine = {
  accountId: number;
  side: "DEBIT" | "CREDIT";
  amount: string;
  partnerId?: number;
  departmentId?: number;
};
const STATUS: Record<string, { label: string; tone: "normal" | "warning" }> = {
  draft: { label: "작성 중", tone: "normal" },
  confirmed: { label: "확정", tone: "normal" },
  reversed: { label: "역분개됨", tone: "warning" },
};
const today = () => new Date().toISOString().slice(0, 10);

export function JournalEntries() {
  const { data, error, reload } = useLists<
    [Entry[], Account[], Partner[], Dept[]]
  >([
    "/journal-entries",
    "/accounts?limit=200",
    "/partners?limit=200",
    "/departments?limit=200",
  ]);
  const { send, pending, error: saveError, deleteButtons } = useSend(reload);
  const [selectedId, setSelectedId] = useState<number>();
  const [entryDate, setEntryDate] = useState(today());
  const [description, setDescription] = useState("");
  const [lines, setLines] = useState<DraftLine[]>([]);
  const [reason, setReason] = useState("");

  const [entries, accounts, partners, departments] = data ?? [
    undefined,
    [],
    [],
    [],
  ];
  const errors = fieldErrors(saveError);
  const selected = entries?.find((e) => e.id === selectedId);
  if (moduleOff(error)) return <ModuleOff />;

  const sum = (side: "DEBIT" | "CREDIT") =>
    lines
      .filter((l) => l.side === side)
      .reduce((total, l) => total + Number(l.amount || 0), 0);

  async function create() {
    const made = await send<{ id: number }>("/journal-entries", "POST", {
      entryDate,
      description: description || undefined,
    });
    if (made?.id) {
      setSelectedId(made.id);
      setLines([]);
    }
  }

  return (
    <div className="page-fill">
      <PageTitle
        id="E-30"
        title="전표 입력·조회"
        help="erp/e-30"
        actions={
          <button
            type="button"
            disabled={pending}
            onClick={() => void create()}
          >
            일반전표 등록
          </button>
        }
      />
      <p className="muted" role="note">
        확정 조건은 넷입니다 — 차변 합 = 대변 합 &gt; 0, 라인 둘 이상, 계정이
        요구하는 거래처·부서가 채워짐, 그 달이 마감되지 않음. 확정한 전표는
        고치지 않습니다. 틀렸으면 역분개로 반대 전표를 만듭니다. 업무에서
        자동으로 생긴 전표도 여기서 함께 봅니다.
      </p>
      <ErrorNotice error={error} retry={reload} />
      <ErrorNotice error={saveError} />
      {!entries ? (
        <Loading />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <DataTable
              rows={entries}
              columns={[
                { key: "entryNo", label: "전표 번호" },
                { key: "entryDate", label: "일자" },
                { key: "entryKind", label: "종류" },
                {
                  // 소명 전표는 번호가 전표 1건을 가리키지 않아 원천 번호가 비어 있다.
                  // 그래도 자동 전표다 — '수동'은 원천이 아예 없는 일반전표뿐이다.
                  key: "sourceRef",
                  label: "원천",
                  wrap: true,
                  render: (e) =>
                    e.sourceRef ??
                    (e.sourceKind ? (e.description ?? "자동") : "수동"),
                },
                {
                  key: "debitTotal",
                  label: "금액",
                  render: (e) => won(e.debitTotal),
                },
                {
                  key: "status",
                  label: "상태",
                  render: (e) => (
                    <Badge tone={STATUS[e.status].tone}>
                      {STATUS[e.status].label}
                    </Badge>
                  ),
                },
                {
                  key: "id",
                  label: "관리",
                  render: (e) => (
                    <button
                      type="button"
                      className="link-button"
                      onClick={() => setSelectedId(e.id)}
                    >
                      열기
                    </button>
                  ),
                },
              ]}
              caption="전표"
              offset={0}
              total={entries.length}
              limit={entries.length || 1}
              onPage={() => undefined}
              empty="전표가 없습니다."
            />
            {selected && (
              <section className="section-block">
                <div className="section-heading">
                  <h2>{selected.entryNo}</h2>
                  <Badge tone={STATUS[selected.status].tone}>
                    {STATUS[selected.status].label}
                  </Badge>
                </div>
                {selected.reversalOfNo && (
                  <p role="note">{selected.reversalOfNo}의 역분개입니다.</p>
                )}
                {selected.reversedByNo && (
                  <p role="note">
                    {selected.reversedByNo}로 역분개됐습니다. 이 전표는 장부에
                    남지만 잔액에는 서로 상쇄됩니다.
                  </p>
                )}
                <DataTable
                  rows={selected.lines}
                  columns={[
                    {
                      key: "side",
                      label: "차·대",
                      render: (l) => (l.side === "DEBIT" ? "차변" : "대변"),
                    },
                    {
                      key: "accountCode",
                      label: "계정",
                      render: (l) => `${l.accountCode} ${l.accountName}`,
                    },
                    {
                      key: "amount",
                      label: "금액",
                      render: (l) => won(l.amount),
                    },
                    {
                      key: "partnerCode",
                      label: "거래처",
                      render: (l) => l.partnerCode ?? "—",
                    },
                    {
                      key: "departmentCode",
                      label: "부서",
                      render: (l) => l.departmentCode ?? "—",
                    },
                  ]}
                  caption="전표 라인"
                  offset={0}
                  total={selected.lines.length}
                  limit={selected.lines.length || 1}
                  onPage={() => undefined}
                  empty="라인이 없습니다."
                />
                <p>
                  차변 {won(selected.debitTotal)} · 대변{" "}
                  {won(selected.creditTotal)}
                </p>
                {selected.status === "draft" && (
                  <div className="section-block">
                    <h3>라인 편집</h3>
                    {lines.map((line, index) => (
                      <div className="field-row" key={index}>
                        <select
                          aria-label={`${index + 1}번째 계정`}
                          value={line.accountId || ""}
                          onChange={(e) =>
                            setLines(
                              lines.map((l, i) =>
                                i === index
                                  ? { ...l, accountId: Number(e.target.value) }
                                  : l,
                              ),
                            )
                          }
                        >
                          <option value="">계정 선택</option>
                          {accounts
                            .filter((a) => a.isActive)
                            .map((a) => (
                              <option key={a.id} value={a.id}>
                                {a.accountCode} {a.accountName}
                              </option>
                            ))}
                        </select>
                        <select
                          aria-label={`${index + 1}번째 차대`}
                          value={line.side}
                          onChange={(e) =>
                            setLines(
                              lines.map((l, i) =>
                                i === index
                                  ? {
                                      ...l,
                                      side: e.target.value as
                                        "DEBIT" | "CREDIT",
                                    }
                                  : l,
                              ),
                            )
                          }
                        >
                          <option value="DEBIT">차변</option>
                          <option value="CREDIT">대변</option>
                        </select>
                        <Field
                          label={`${index + 1}번째 금액`}
                          value={line.amount}
                          onChange={(e) =>
                            setLines(
                              lines.map((l, i) =>
                                i === index
                                  ? { ...l, amount: e.target.value }
                                  : l,
                              ),
                            )
                          }
                        />
                        <select
                          aria-label={`${index + 1}번째 거래처`}
                          value={line.partnerId ?? ""}
                          onChange={(e) =>
                            setLines(
                              lines.map((l, i) =>
                                i === index
                                  ? {
                                      ...l,
                                      partnerId: e.target.value
                                        ? Number(e.target.value)
                                        : undefined,
                                    }
                                  : l,
                              ),
                            )
                          }
                        >
                          <option value="">거래처 없음</option>
                          {partners.map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.partnerCode} {p.partnerName}
                            </option>
                          ))}
                        </select>
                        <select
                          aria-label={`${index + 1}번째 부서`}
                          value={line.departmentId ?? ""}
                          onChange={(e) =>
                            setLines(
                              lines.map((l, i) =>
                                i === index
                                  ? {
                                      ...l,
                                      departmentId: e.target.value
                                        ? Number(e.target.value)
                                        : undefined,
                                    }
                                  : l,
                              ),
                            )
                          }
                        >
                          <option value="">부서 없음</option>
                          {departments.map((d) => (
                            <option key={d.id} value={d.id}>
                              {d.code} {d.name}
                            </option>
                          ))}
                        </select>
                        <button
                          type="button"
                          className="link-button"
                          onClick={() =>
                            setLines(lines.filter((_, i) => i !== index))
                          }
                        >
                          줄 삭제
                        </button>
                      </div>
                    ))}
                    {errors.lines && <small role="alert">{errors.lines}</small>}
                    <p>
                      입력 중 차변 {sum("DEBIT").toLocaleString()} · 대변{" "}
                      {sum("CREDIT").toLocaleString()}
                    </p>
                    <button
                      type="button"
                      onClick={() =>
                        setLines([
                          ...lines,
                          { accountId: 0, side: "DEBIT", amount: "" },
                        ])
                      }
                    >
                      줄 추가
                    </button>
                    <button
                      type="button"
                      disabled={pending || !lines.length}
                      onClick={() =>
                        void send(
                          `/journal-entries/${selected.id}/lines`,
                          "PUT",
                          { lines },
                        )
                      }
                    >
                      라인 저장
                    </button>
                    <button
                      type="button"
                      disabled={pending}
                      onClick={() =>
                        void send(
                          `/journal-entries/${selected.id}/confirm`,
                          "POST",
                        )
                      }
                    >
                      확정
                    </button>
                    {deleteButtons(
                      String(selected.id),
                      `/journal-entries/${selected.id}`,
                    )}
                  </div>
                )}
                {selected.status === "confirmed" && (
                  <div className="row-actions">
                    <Field
                      label="역분개 사유"
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                    />
                    <button
                      type="button"
                      className="secondary"
                      disabled={pending || reason.trim().length < 1}
                      onClick={() =>
                        void send(
                          `/journal-entries/${selected.id}/reverse`,
                          "POST",
                          { reason },
                        )
                      }
                    >
                      역분개
                    </button>
                  </div>
                )}
              </section>
            )}
          </section>
          <section className="section-block">
            <h2>새 일반전표</h2>
            <label>
              일자
              <input
                type="date"
                value={entryDate}
                onChange={(e) => setEntryDate(e.target.value)}
              />
            </label>
            <Field
              label="적요"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
            <p className="muted">
              등록하면 작성 중 전표가 생깁니다. 라인을 넣고 확정하세요.
            </p>
          </section>
        </div>
      )}
    </div>
  );
}
