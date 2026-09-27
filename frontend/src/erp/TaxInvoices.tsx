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
  type Column,
  useDiscardGuard,
} from "../shared/components";
import {
  fieldErrors,
  labels,
  ModuleOff,
  moduleOff,
  PARTNERS,
  useLists,
  useSend,
  won,
  type Partner,
} from "./common";
import { INVOICE, type Sale } from "./SalesRecords";

type Invoice = {
  id: number;
  salesRecordId: number;
  partnerId: number;
  status: "pending" | "issued";
  approvalNo: string | null;
  issuedOn: string | null;
  totalAmount: string;
  recognizedAt: string;
  shipmentNo: string;
};
const today = () => new Date().toLocaleDateString("sv-SE");

type PanelState =
  { type: "create" } | { type: "issue"; invoice: Invoice } | null;

export function TaxInvoices() {
  const { data, error, reload } = useLists<[Invoice[], Sale[], Partner[]]>([
    "/tax-invoices",
    "/sales-records",
    PARTNERS,
  ]);
  const { send, pending, error: saveError, setError } = useSend(reload);
  const [panel, setPanel] = useState<PanelState>(null);
  const [saleId, setSaleId] = useState(0);
  const [issue, setIssue] = useState({ approvalNo: "", issuedOn: today() });

  const [invoices, sales, partners] = data ?? [undefined, [], []];
  const name = labels(partners, []);
  const errors = fieldErrors(saveError);
  // 발급 대상: 취소 안 된, 계산서 없는 매출. 0원 매출은 발급하지 않는다(E-G07).
  const eligible = sales.filter(
    (s) => !s.cancelledAt && !s.taxInvoiceId && Number(s.totalAmount) > 0,
  );

  const dirty =
    panel?.type === "create"
      ? saleId !== 0
      : panel?.type === "issue"
        ? issue.approvalNo !== "" || issue.issuedOn !== today()
        : false;
  const guard = useDiscardGuard(dirty);

  if (moduleOff(error)) return <ModuleOff />;

  function closePanel() {
    setPanel(null);
    setSaleId(0);
    setIssue({ approvalNo: "", issuedOn: today() });
    setError(undefined);
  }

  function openIssue(invoice: Invoice) {
    setPanel({ type: "issue", invoice });
    setIssue({ approvalNo: "", issuedOn: today() });
    setError(undefined);
  }

  async function create(event: FormEvent) {
    event.preventDefault();
    if (pending || !saleId) return;
    const created = await send<Invoice>("/tax-invoices", "POST", {
      salesRecordId: saleId,
    });
    if (created) {
      setSaleId(0);
      setPanel(null);
    }
  }

  async function submitIssue(event: FormEvent) {
    event.preventDefault();
    if (panel?.type !== "issue" || pending) return;
    const saved = await send(
      `/tax-invoices/${panel.invoice.id}/issue`,
      "POST",
      {
        approvalNo: issue.approvalNo.trim(),
        issuedOn: issue.issuedOn,
      },
    );
    if (saved) {
      closePanel();
    }
  }

  const columns: Column<Invoice>[] = [
    { key: "shipmentNo", label: "매출(출하번호)" },
    {
      key: "id",
      label: "관리",
      render: (r) =>
        r.status === "pending" ? (
          <button
            type="button"
            className="link-button"
            aria-pressed={panel?.type === "issue" && panel.invoice.id === r.id}
            onClick={() => guard.guard(() => openIssue(r))}
          >
            발급
          </button>
        ) : (
          "-"
        ),
    },
    {
      key: "partnerId",
      label: "거래처",
      render: (r) => name.partner(r.partnerId),
    },
    { key: "totalAmount", label: "합계", render: (r) => won(r.totalAmount) },
    {
      key: "status",
      label: "상태",
      render: (r) => (
        <Badge tone={r.status === "issued" ? "normal" : "warning"}>
          {INVOICE[r.status]}
        </Badge>
      ),
    },
    {
      key: "approvalNo",
      label: "승인번호",
      render: (r) => r.approvalNo ?? "-",
    },
    { key: "issuedOn", label: "발급일", render: (r) => r.issuedOn ?? "-" },
  ];

  return (
    <div className="page-fill">
      <PageTitle
        id="E-08"
        title="세금계산서"
        subtitle="매출 1건마다 세금계산서를 만들고 발급을 기록합니다"
        help="erp/e-08"
        actions={
          <button
            type="button"
            aria-pressed={panel?.type === "create"}
            onClick={() =>
              guard.guard(() =>
                panel?.type === "create"
                  ? closePanel()
                  : setPanel({ type: "create" }),
              )
            }
          >
            계산서 만들기
          </button>
        }
      />
      <p className="muted">
        실제 운영에서는 전자세금계산서 연동이 필요하며 1차 범위에서
        제외했습니다. 승인번호와 발급일은 직접 입력하며, 국세청 승인을 검증한
        값이 아닙니다. 0원 매출은 세금계산서를 발급하지 않습니다.
      </p>
      <ErrorNotice error={Object.keys(errors).length ? undefined : saveError} />
      <ErrorNotice error={error} retry={reload} />
      {!invoices ? (
        !error && <Loading />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <div className="section-block">
              <DataTable
                rows={invoices}
                columns={columns}
                caption="세금계산서 목록"
                offset={0}
                total={invoices.length}
                limit={invoices.length || 1}
                onPage={() => undefined}
                empty={
                  <EmptyState
                    reason="세금계산서가 없습니다. 패널을 열어 매출을 골라 만드세요."
                    action="계산서 만들기"
                    onAction={() =>
                      guard.guard(() => setPanel({ type: "create" }))
                    }
                  />
                }
              />
            </div>
          </section>

          {panel?.type === "create" && (
            <FormPanel
              title="새 세금계산서"
              guard={guard}
              onClose={() => guard.guard(closePanel)}
              onSubmit={(e) => void create(e)}
              actions={
                <>
                  <button
                    type="submit"
                    disabled={pending || !saleId}
                    aria-busy={pending}
                  >
                    발급대기로 만들기
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => guard.guard(closePanel)}
                  >
                    취소
                  </button>
                </>
              }
            >
              <ErrorNotice error={saveError} />
              <div className="field">
                <label htmlFor="tax-invoice-sale">매출</label>
                <select
                  id="tax-invoice-sale"
                  value={saleId || ""}
                  onChange={(e) => setSaleId(Number(e.target.value))}
                >
                  <option value="">매출 선택</option>
                  {eligible.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.shipmentNo} · {name.partner(s.partnerId)} ·{" "}
                      {won(s.totalAmount)}
                    </option>
                  ))}
                </select>
              </div>
              <p className="muted">
                취소되지 않았고 계산서가 없는 매출만 고를 수 있습니다.
              </p>
            </FormPanel>
          )}

          {panel?.type === "issue" && (
            <FormPanel
              title={`${panel.invoice.shipmentNo} 발급`}
              guard={guard}
              onClose={() => guard.guard(closePanel)}
              onSubmit={(e) => void submitIssue(e)}
              actions={
                <>
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    발급완료로 기록
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => guard.guard(closePanel)}
                  >
                    취소
                  </button>
                </>
              }
            >
              <ErrorNotice error={saveError} />
              <Field
                label="승인번호"
                value={issue.approvalNo}
                required
                maxLength={60}
                error={errors.approvalNo}
                onChange={(e) =>
                  setIssue({ ...issue, approvalNo: e.target.value })
                }
              />
              <Field
                label="발급일"
                type="date"
                value={issue.issuedOn}
                required
                error={errors.issuedOn}
                onChange={(e) =>
                  setIssue({ ...issue, issuedOn: e.target.value })
                }
              />
            </FormPanel>
          )}
        </div>
      )}
    </div>
  );
}
