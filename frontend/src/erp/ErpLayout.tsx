// ERP 솔루션 레이아웃: 좌측 사이드바 + 포털 공통 헤더 (FS-008a 포털 §6-5)
import { useLayoutEffect, useRef } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
// 구현된 화면만 메뉴에 둔다. 준비 중 항목을 나열하지 않는다(FS-008a 포털 §1).
export const erpScreens = [
  { path: "dashboard", id: "E-01", label: "대시보드", group: "개요" },
  { path: "quotations", id: "E-02", label: "견적", group: "영업" },
  { path: "sales-plans", id: "E-03", label: "판매계획", group: "영업" },
  { path: "sales-orders", id: "E-04", label: "수주", group: "영업" },
  {
    path: "shipment-orders",
    id: "E-05",
    label: "출하지시",
    group: "출하·매출",
  },
  { path: "shipments", id: "E-06", label: "출하", group: "출하·매출" },
  { path: "sales-records", id: "E-07", label: "매출", group: "출하·매출" },
  {
    path: "tax-invoices",
    id: "E-08",
    label: "세금계산서",
    group: "출하·매출",
  },
  {
    path: "receivables",
    id: "E-09",
    label: "매출채권 현황",
    group: "채권·수금",
  },
  {
    path: "receipts",
    id: "E-10",
    label: "수금 등록·소명",
    group: "채권·수금",
  },
  {
    path: "purchase-invoices",
    id: "E-11",
    label: "매입 전표",
    group: "매입·채무",
  },
  { path: "payables", id: "E-12", label: "매입채무 현황", group: "매입·채무" },
  {
    path: "payments",
    id: "E-13",
    label: "지급 등록·소명",
    group: "매입·채무",
  },
  {
    path: "journal-preview",
    id: "E-14",
    label: "분개 미리보기",
    group: "회계",
  },
  { path: "partners", id: "E-15", label: "거래처", group: "기준정보" },
  { path: "items", id: "E-16", label: "품목", group: "기준정보" },
  {
    path: "partner-prices",
    id: "E-17",
    label: "거래처별 단가",
    group: "기준정보",
  },
  {
    path: "accounts",
    id: "E-18",
    label: "계정과목·분개규칙",
    group: "기준정보",
  },
];
export function ErpLayout() {
  const location = useLocation();
  const detailsRef = useRef<HTMLDetailsElement>(null);
  const currentScreen = erpScreens.find(
    (s) =>
      location.pathname === `/erp/${s.path}` ||
      location.pathname.startsWith(`/erp/${s.path}/`),
  );

  // 접는 메뉴는 좁은 화면에서만 닫는다. 넓은 화면은 summary가 숨겨져(styles.css 801px 이상)
  // 다시 열 방법이 없으므로 절대 닫지 않는다. 기준 800px은 styles.css의 미디어 쿼리와 같다.
  // matchMedia가 없는 환경은 넓은 화면으로 본다(닫지 않는 쪽이 안전하다).
  const collapsible = () =>
    window.matchMedia?.("(max-width: 800px)").matches ?? false;
  const closeMenu = () => {
    if (detailsRef.current && collapsible()) detailsRef.current.open = false;
  };
  // 좁은 화면은 닫힌 상태로 시작한다. 그리기 전에 실행해 펼쳐진 메뉴가 깜빡이지 않는다.
  useLayoutEffect(closeMenu, []);

  const summaryTitle = currentScreen
    ? `ERP 메뉴 · ${currentScreen.id} ${currentScreen.label}`
    : "ERP 메뉴";

  return (
    <div className="solution-layout">
      <aside className="solution-sidebar" aria-label="ERP 메뉴">
        <details ref={detailsRef} open className="solution-sidebar-details">
          <summary>{summaryTitle}</summary>
          <p className="eyebrow">ERP 경영관리</p>
          <nav>
            {[...new Set(erpScreens.map((s) => s.group))].map((group) => (
              <section key={group}>
                <h2>{group}</h2>
                {erpScreens
                  .filter((s) => s.group === group)
                  .map((s) => (
                    <NavLink
                      key={s.path}
                      to={`/erp/${s.path}`}
                      onClick={closeMenu}
                    >
                      <span>{s.id}</span> {s.label}
                    </NavLink>
                  ))}
              </section>
            ))}
            <section>
              <h2>다른 앱</h2>
              <NavLink to="/mes" onClick={closeMenu}>
                MES 생산관리
              </NavLink>
              <NavLink to="/fems" onClick={closeMenu}>
                FEMS 에너지관리
              </NavLink>
              <NavLink to="/home" onClick={closeMenu}>
                포털 홈
              </NavLink>
            </section>
          </nav>
        </details>
      </aside>
      <div className="solution-content">
        <Outlet />
      </div>
    </div>
  );
}
