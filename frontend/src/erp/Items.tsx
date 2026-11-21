import { useEffect, useState } from "react";
import { useSession } from "../app/session";
import { ErrorNotice } from "../shared/components";
import { Master, allRows, type InputField, type Row } from "./Master";
const fields: InputField[] = [
  { key: "itemCode", label: "품목 코드", maxLength: 40 },
  { key: "name", label: "품목명", maxLength: 100 },
  {
    key: "baseUnit",
    label: "기준 단위",
    options: ["EA", "BOX", "KG", "M", "L", "SET"].map((x) => [x, x]),
    initial: "EA",
  },
  {
    key: "itemType",
    label: "품목 구분",
    options: [
      ["finished", "완제품"],
      ["semi_finished", "반제품"],
      ["raw", "원재료"],
      ["auxiliary", "부자재"],
      ["merchandise", "상품"],
      ["intangible", "무형"],
    ],
    initial: "finished",
  },
  {
    key: "taxCategory",
    label: "과세 구분",
    options: [
      ["TAXABLE", "과세"],
      ["ZERO", "영세"],
      ["EXEMPT", "면세"],
    ],
    initial: "TAXABLE",
  },
  { key: "isActive", label: "사용 여부", type: "checkbox" },
  { key: "spec", label: "규격", nullable: true, maxLength: 100 },
  { key: "standardCost", label: "표준 원가", nullable: true },
  { key: "standardPrice", label: "표준 판매가", nullable: true },
  { key: "trackStock", label: "재고 관리", type: "checkbox" },
];
const conversions: InputField[] = [
  { key: "fromUnit", label: "환산 전 단위", maxLength: 10 },
  { key: "factor", label: "환산 계수", initial: "1" },
];
const extra: InputField[] = [{ key: "toUnit", label: "환산 후 기준 단위" }];
export function Items() {
  const { fail } = useSession();
  const [items, setItems] = useState<Row[]>([]);
  const [selected, setSelected] = useState(0);
  const [reload, setReload] = useState(0);
  const [error, setError] = useState<unknown>();
  useEffect(() => {
    const controller = new AbortController();
    allRows("/api/v1/erp/items", controller.signal)
      .then(setItems)
      .catch((e) => {
        if (!controller.signal.aborted) {
          setError(e);
          fail(e);
        }
      });
    return () => controller.abort();
  }, [reload]);
  return (
    <Master
      id="E-16"
      title="품목"
      path="/api/v1/erp/items"
      fields={fields}
      note="MES 품목과 독립 — 이 품목은 ERP 전용입니다. MES 품목과 코드가 같아도 별개 데이터입니다. 표준 판매가는 거래처별 단가와 단가 그룹이 모두 없을 때 쓰는 마지막 단가이고, 무형 품목처럼 재고를 잡지 않는 것은 재고 관리를 끕니다."
    >
      <section className="section-block">
        <div className="section-heading">
          <h2>품목별 단위환산</h2>
        </div>
        <p>
          환산 전 수량 × 계수 = 기준 단위 수량. 기준 단위는 선택한 품목에서
          결정합니다.
        </p>
        <ErrorNotice error={error} />
        <label>
          환산할 품목
          <select
            aria-label="환산할 품목"
            value={selected}
            onChange={(e) => setSelected(Number(e.target.value))}
          >
            <option value={0}>품목 선택</option>
            {items.map((r) => (
              <option key={r.id} value={r.id}>
                {r.itemCode} · {r.name} ({r.baseUnit})
              </option>
            ))}
          </select>
        </label>
        <button type="button" onClick={() => setReload((n) => n + 1)}>
          품목 목록 새로고침
        </button>
      </section>
      {selected > 0 && (
        <Master
          key={selected}
          embedded
          id="E-16"
          title="단위환산"
          path={`/api/v1/erp/items/${selected}/conversions`}
          fields={conversions}
          extraColumns={extra}
        />
      )}
    </Master>
  );
}
