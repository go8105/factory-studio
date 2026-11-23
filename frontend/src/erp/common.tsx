// ERP 영업·출하 화면 공통: 공통 훅(shared/hooks)에 ERP 접두사, 금액·수량 표시, 거래처·품목 이름
import { EmptyState } from "../shared/components";
import { useApiLists, useApiSend } from "../shared/hooks";
export { fieldErrors, moduleOff } from "../shared/hooks";

export const ERP = "/api/v1/erp";
export type Partner = {
  id: number;
  partnerCode: string;
  partnerName: string;
  partnerKind: "CUSTOMER" | "SUPPLIER" | "BOTH";
  isActive: boolean;
};
export type Item = {
  id: number;
  itemCode: string;
  name: string;
  baseUnit: string;
  isActive: boolean;
  itemType: string;
  trackStock: boolean;
};
// 기준정보 목록은 페이지 API다. 영업 화면 선택지에는 한 번에 최대 200건을 쓴다.
export const PARTNERS = "/partners?limit=200";
export const ITEMS = "/items?limit=200";

export const useLists = <T extends unknown[]>(paths: string[]) =>
  useApiLists<T>(ERP, paths);
export const useSend = (onDone: () => void) => useApiSend(ERP, onDone);

export const won = (value: string) => `${Number(value).toLocaleString()}원`;
export const qty = (value: string) => Number(value).toLocaleString();

export function labels(partners: Partner[], items: Item[]) {
  return {
    partner: (id: number) => {
      const p = partners.find((x) => x.id === id);
      return p ? `${p.partnerCode} ${p.partnerName}` : String(id);
    },
    item: (id: number) => {
      const i = items.find((x) => x.id === id);
      return i ? `${i.itemCode} ${i.name}` : String(id);
    },
  };
}

// 매출·매입을 함께 하는 거래처(BOTH)는 양쪽 목록에 모두 나온다(DSN-11 F02).
export const customers = (partners: Partner[]) =>
  partners.filter(
    (p) => ["CUSTOMER", "BOTH"].includes(p.partnerKind) && p.isActive,
  );

export const suppliers = (partners: Partner[]) =>
  partners.filter(
    (p) => ["SUPPLIER", "BOTH"].includes(p.partnerKind) && p.isActive,
  );

export function ModuleOff() {
  return (
    <EmptyState
      reason="ERP를 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다."
      to="/workspace"
      action="내 공간으로"
    />
  );
}

// 조회 화면의 기간 고르개. 현황(E-21·E-25)과 장부(E-32~E-34)가 같은 것을 쓴다.
export const today = () => new Date().toISOString().slice(0, 10);
export const monthsAgo = (n: number) => {
  const d = new Date();
  d.setMonth(d.getMonth() - n);
  return d.toISOString().slice(0, 10);
};
export const monthStart = () => today().slice(0, 7) + "-01";

export function Period({
  from,
  to,
  set,
}: {
  from: string;
  to: string;
  set: (patch: { from?: string; to?: string }) => void;
}) {
  return (
    <span className="row-actions">
      <label>
        시작
        <input
          type="date"
          value={from}
          onChange={(e) => set({ from: e.target.value })}
        />
      </label>
      <label>
        끝
        <input
          type="date"
          value={to}
          onChange={(e) => set({ to: e.target.value })}
        />
      </label>
    </span>
  );
}
