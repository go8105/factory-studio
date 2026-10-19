// W-17 라벨 출력 — 위치 라벨·자재 LOT 라벨을 Code128로 브라우저에서 인쇄한다 (DSN-13 F07·F13).
// 대상당 유효 라벨은 1건이다. 같은 대상을 다시 찍으면 사유를 받고 이전 라벨을 무효로 바꾼다.
import { useEffect, useState, type FormEvent } from "react";
import { useSession } from "../app/session";
import { api } from "../shared/api";
import {
  Badge,
  DataTable,
  ErrorNotice,
  Loading,
  PageTitle,
  type Column,
} from "../shared/components";
import {
  fieldErrors,
  LABEL_KIND_LABEL,
  time,
  useLists,
  WMS,
  type LabelKind,
  type LabelPrint,
  type Location,
  type LotRow,
  type Warehouse,
} from "./common";

const LIMIT = 50;

export function Labels() {
  const { session } = useSession();
  const [kind, setKind] = useState<LabelKind>("LOCATION");
  const [value, setValue] = useState("");
  const [copies, setCopies] = useState("1");
  const [reason, setReason] = useState("");
  const [pending, setPending] = useState(false);
  const [actionError, setActionError] = useState<unknown>();
  const [printed, setPrinted] = useState<LabelPrint | null>(null);

  // 위치는 창고별로만 조회된다(/locations 엔드포인트는 없다).
  const [warehouseId, setWarehouseId] = useState("");
  const [locations, setLocations] = useState<Location[]>([]);

  const { data, reload } = useLists<
    [{ rows: LabelPrint[]; total: number }, Warehouse[], LotRow[]]
  >(["/labels?pageSize=50", "/warehouses", "/lots?limit=200"]);

  useEffect(() => {
    setValue("");
    if (!warehouseId) {
      setLocations([]);
      return;
    }
    const stop = new AbortController();
    api<Location[]>(`${WMS}/warehouses/${warehouseId}/locations`, {
      signal: stop.signal,
    })
      .then((res) => !stop.signal.aborted && setLocations(res.data ?? []))
      .catch(() => !stop.signal.aborted && setLocations([]));
    return () => stop.abort();
  }, [warehouseId]);

  if (!data) return <Loading />;

  const rows = data[0]?.rows ?? [];
  const total = data[0]?.total ?? 0;
  const warehouses = data[1] ?? [];
  const lots = data[2] ?? [];
  const errors = fieldErrors(actionError);
  const targets =
    kind === "LOCATION"
      ? locations
          .filter((l) => l.isActive)
          .map((l) => ({ value: l.code, label: `${l.code} ${l.name}` }))
      : lots.map((l) => ({ value: l.lotNo, label: l.lotNo }));

  async function handlePrint(e: FormEvent) {
    e.preventDefault();
    if (!value) return;
    setPending(true);
    setActionError(undefined);
    try {
      const res = await api<LabelPrint>(`${WMS}/labels`, {
        method: "POST",
        csrf: session?.csrfToken,
        key: crypto.randomUUID(),
        body: {
          labelKind: kind,
          barcodeValue: value,
          copies: Number(copies) || 1,
          reprintReason: reason || null,
        },
      });
      setPrinted(res.data);
      setReason("");
      reload();
    } catch (err) {
      setActionError(err);
    } finally {
      setPending(false);
    }
  }

  const columns: Column<LabelPrint>[] = [
    {
      key: "barcodeValue",
      label: "바코드",
      render: (r) => <strong>{r.barcodeValue}</strong>,
    },
    {
      key: "labelKind",
      label: "종류",
      render: (r) => LABEL_KIND_LABEL[r.labelKind],
    },
    {
      key: "status",
      label: "상태",
      render: (r) => (
        <Badge tone={r.status === "VALID" ? "normal" : "warning"}>
          {r.status === "VALID" ? "유효" : "무효"}
        </Badge>
      ),
    },
    { key: "copies", label: "매수", render: (r) => `${r.copies}장` },
    {
      key: "reprintReason",
      label: "재발행 사유",
      render: (r) => r.reprintReason ?? <span className="muted">-</span>,
    },
    { key: "printedAt", label: "출력 일시", render: (r) => time(r.printedAt) },
  ];

  return (
    <div className="wms-labels">
      <PageTitle
        id="W-17"
        title="W-17 라벨 출력"
        subtitle="위치 라벨과 자재 LOT 라벨을 Code128로 인쇄합니다. 같은 대상을 다시 찍으면 사유를 적고 이전 라벨은 무효가 됩니다."
      />

      <form aria-label="라벨 출력" onSubmit={handlePrint} className="card">
        <ErrorNotice error={actionError} />
        <label>
          종류
          <select
            value={kind}
            onChange={(e) => {
              setKind(e.target.value as LabelKind);
              setValue("");
            }}
          >
            <option value="LOCATION">위치 라벨</option>
            <option value="MATERIAL_LOT">자재 LOT 라벨</option>
          </select>
        </label>
        {kind === "LOCATION" && (
          <label>
            창고
            <select
              value={warehouseId}
              onChange={(e) => setWarehouseId(e.target.value)}
              required
            >
              <option value="">선택</option>
              {warehouses.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.code} · {w.name}
                </option>
              ))}
            </select>
          </label>
        )}
        <label>
          대상
          <select
            value={value}
            onChange={(e) => setValue(e.target.value)}
            required
          >
            <option value="">선택</option>
            {targets.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
          {errors.barcodeValue && (
            <span className="field-error">{errors.barcodeValue}</span>
          )}
        </label>
        <label>
          매수
          <input
            value={copies}
            inputMode="numeric"
            onChange={(e) => setCopies(e.target.value)}
          />
        </label>
        <label>
          재발행 사유
          <input
            value={reason}
            maxLength={300}
            placeholder="이미 발행한 대상을 다시 찍을 때만"
            onChange={(e) => setReason(e.target.value)}
          />
          {errors.reprintReason && (
            <span className="field-error">{errors.reprintReason}</span>
          )}
        </label>
        <button type="submit" disabled={pending || !value}>
          라벨 발행
        </button>
      </form>

      {printed && (
        <section className="card" aria-label="인쇄 미리보기">
          <h2>인쇄 미리보기</h2>
          <p className="muted">
            {LABEL_KIND_LABEL[printed.labelKind]} · {printed.copies}장
            {printed.reprintOfId ? " · 재발행" : ""}
          </p>
          <div
            style={{
              border: "1px solid var(--line)",
              borderRadius: 4,
              padding: "1rem",
              textAlign: "center",
              maxWidth: 320,
            }}
          >
            <div style={{ fontSize: "1.5rem", letterSpacing: "0.1em" }}>
              {printed.barcodeValue}
            </div>
            <div className="muted">Code128</div>
          </div>
          <button type="button" onClick={() => window.print()}>
            인쇄
          </button>
        </section>
      )}

      <DataTable
        caption="라벨 출력 기록"
        rows={rows}
        columns={columns}
        offset={0}
        limit={LIMIT}
        total={total}
        onPage={() => reload()}
      />
    </div>
  );
}
