"""E-35 월 마감·기초 잔액 (DSN-11 F57·F58).

- **마감은 자물쇠다.** 마감한 달에는 전표를 넣지도 확정하지도 역분개하지도 못한다(1e `posting.month_closed`).
  업무 자체는 막지 않는다 — 확정은 되고 전표만 E-31에 남는다. 회계가 공장을 세우지 않는다.
- 마감 전에 **작성 중인 전표**가 있으면 막는다. 확정하든 지우든 사람이 정하고 나서 닫는다.
  미반영 업무는 막지 않고 **세어서 보여 준다** — 규칙이 없어 영영 못 넣는 것도 있어서,
  막으면 달을 닫지 못하는 덫이 된다. 닫을지는 사람이 본 뒤에 정한다.
- 해제는 **다음 달이 열려 있을 때만** 한다. 닫힌 달 사이에 구멍을 내지 않는다.
- 기초 잔액은 연도·계정(·거래처)당 1건이다. 연도 이월은 전년 12월 마감 잔액으로 **새 행**을 만든다.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import text

from fs.common.scope import read_scope
from fs.erp import posting
from fs.erp.sales import _S, MODULE, _action, _locked, _rows, _s
from fs.erp.service import _read, invalid

ZERO = Decimal(0)
RETAINED = "RETAINED_EARNINGS"
BALANCE_SHEET = ("ASSET", "LIABILITY", "EQUITY")

PERIOD_SQL = """
SELECT to_char(j.entry_date, 'YYYY-MM') period_month,
       count(*) FILTER (WHERE j.status IN ('confirmed', 'reversed')) posted_count,
       count(*) FILTER (WHERE j.status='draft') draft_count
FROM erp.journal_entry j
WHERE j.workspace_id=:w AND j.generation_id=:g
  AND to_char(j.entry_date, 'YYYY')=:year
GROUP BY 1"""
STATUS_SQL = f"""
SELECT period_month, status, closed_at FROM erp.fiscal_period
WHERE {_S} AND period_month LIKE :like ORDER BY period_month"""
# 전년 잔액(차변 양수). 거래처는 관리항목이 필요한 계정만 따로 남긴다.
CARRY_SQL = """
WITH moves AS (
  SELECT l.account_id,
         CASE WHEN a.requires_partner THEN l.partner_id END partner_id,
         a.account_class,
         sum(CASE WHEN l.side='DEBIT' THEN l.amount ELSE -l.amount END) amount
  FROM erp.journal_line l
  JOIN erp.journal_entry j ON j.workspace_id=l.workspace_id
   AND j.generation_id=l.generation_id AND j.id=l.journal_entry_id
   AND j.status IN ('confirmed', 'reversed')
  JOIN erp.account a ON a.workspace_id=l.workspace_id
   AND a.generation_id=l.generation_id AND a.id=l.account_id
  WHERE l.workspace_id=:w AND l.generation_id=:g
    AND to_char(j.entry_date, 'YYYY')=:year
  GROUP BY 1, 2, 3
  UNION ALL
  SELECT o.account_id,
         CASE WHEN a.requires_partner THEN o.partner_id END,
         a.account_class,
         sum(CASE WHEN o.side='DEBIT' THEN o.amount ELSE -o.amount END)
  FROM erp.opening_balance o
  JOIN erp.account a ON a.workspace_id=o.workspace_id
   AND a.generation_id=o.generation_id AND a.id=o.account_id
  WHERE o.workspace_id=:w AND o.generation_id=:g AND o.fiscal_year=:year
  GROUP BY 1, 2, 3
)
SELECT account_id, partner_id, account_class, sum(amount) amount
FROM moves GROUP BY 1, 2, 3"""


def _months(year: str) -> list[str]:
    return [f"{year}-{m:02d}" for m in range(1, 13)]


def _closed(connection, scoped, month: str) -> bool:
    return bool(
        connection.execute(
            text(
                f"SELECT 1 FROM erp.fiscal_period WHERE {_S} AND period_month=:m "
                "AND status='closed'"
            ),
            {**_s(scoped), "m": month},
        ).first()
    )


def list_periods(context, year: str):
    """한 해 12달. 전표 수·작성 중·미반영을 함께 돌려준다. 닫기 전에 보라고 있는 수다."""
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        counts = {
            r["periodMonth"]: r
            for r in _rows(connection, PERIOD_SQL, {**_s(scoped), "year": year})
        }
        marks = {
            r["periodMonth"]: r
            for r in _rows(connection, STATUS_SQL, {**_s(scoped), "like": f"{year}-%"})
        }
        pending = posting.pending(connection, scoped)
    unposted: dict[str, int] = {}
    for row in pending:
        unposted[str(row["entryDate"])[:7]] = (
            unposted.get(str(row["entryDate"])[:7], 0) + 1
        )
    return [
        {
            "periodMonth": month,
            "status": marks.get(month, {}).get("status", "open"),
            "closedAt": marks.get(month, {}).get("closedAt"),
            "postedCount": counts.get(month, {}).get("postedCount", 0),
            "draftCount": counts.get(month, {}).get("draftCount", 0),
            "unpostedCount": unposted.get(month, 0),
        }
        for month in _months(year)
    ]


def close_month(context, month: str, key: str):
    def run(connection, scoped):
        if _closed(connection, scoped, month):
            raise _locked("이미 마감한 달입니다.", "ALREADY_CLOSED")
        drafts = connection.execute(
            text(
                f"SELECT count(*) FROM erp.journal_entry WHERE {_S} "
                "AND to_char(entry_date, 'YYYY-MM')=:m AND status='draft'"
            ),
            {**_s(scoped), "m": month},
        ).scalar_one()
        if drafts:
            raise _locked(
                f"작성 중인 전표가 {drafts}건 있습니다. 확정하거나 지운 뒤 마감하세요.",
                "DRAFT_ENTRIES",
                count=drafts,
            )
        connection.execute(
            text(
                "INSERT INTO erp.fiscal_period (workspace_id, generation_id, "
                "period_month, status, closed_at) VALUES (:w, :g, :m, 'closed', now()) "
                "ON CONFLICT (workspace_id, generation_id, period_month) DO UPDATE "
                "SET status='closed', closed_at=now()"
            ),
            {**_s(scoped), "m": month},
        )
        return _period(connection, scoped, month), "fiscal_period", 0

    return _action(context, "erp.fiscal_period.close", key, {"month": month}, run)


def reopen_month(context, month: str, key: str):
    def run(connection, scoped):
        if not _closed(connection, scoped, month):
            raise _locked("마감한 달이 아닙니다.", "NOT_CLOSED")
        year, part = month.split("-")
        nxt = f"{int(year) + 1}-01" if part == "12" else f"{year}-{int(part) + 1:02d}"
        if _closed(connection, scoped, nxt):
            raise _locked(
                f"다음 달({nxt})이 마감돼 있습니다. 뒤에서부터 해제하세요.",
                "NEXT_MONTH_CLOSED",
            )
        connection.execute(
            text(
                "UPDATE erp.fiscal_period SET status='open', closed_at=NULL "
                f"WHERE {_S} AND period_month=:m"
            ),
            {**_s(scoped), "m": month},
        )
        return _period(connection, scoped, month), "fiscal_period", 0

    return _action(context, "erp.fiscal_period.reopen", key, {"month": month}, run)


def _period(connection, scoped, month: str) -> dict[str, Any]:
    found = _rows(connection, STATUS_SQL, {**_s(scoped), "like": month})
    return found[0] if found else {"periodMonth": month, "status": "open"}


def carry_forward(context, fiscal_year: str, key: str):
    """F58. 전년 12월 마감 잔액으로 다음 해 기초 잔액을 만든다.

    재무상태표 계정은 계정(·거래처)별로 그대로, 손익 계정은 모아서 이월이익잉여금으로 옮긴다.
    손익 계정 잔액을 그대로 이월하면 작년 매출이 올해 매출로 둔갑한다.
    """
    nxt = f"{int(fiscal_year) + 1:04d}"

    def run(connection, scoped):
        if not _closed(connection, scoped, f"{fiscal_year}-12"):
            raise _locked(f"{fiscal_year}년 12월을 먼저 마감하세요.", "YEAR_NOT_CLOSED")
        if connection.execute(
            text(f"SELECT 1 FROM erp.opening_balance WHERE {_S} AND fiscal_year=:y"),
            {**_s(scoped), "y": nxt},
        ).first():
            raise _locked(
                f"{nxt}년 기초 잔액이 이미 있습니다. 지운 뒤 다시 이월하세요.",
                "ALREADY_CARRIED",
            )
        rows = connection.execute(
            text(CARRY_SQL), {**_s(scoped), "year": fiscal_year}
        ).all()
        retained_id = connection.execute(
            text(f"SELECT id FROM erp.account WHERE {_S} AND account_code=:code"),
            {**_s(scoped), "code": RETAINED},
        ).scalar_one_or_none()
        carried: dict[tuple[int, int | None], Decimal] = {}
        profit = ZERO
        for row in rows:
            if row.account_class in BALANCE_SHEET:
                point = (row.account_id, row.partner_id)
                carried[point] = carried.get(point, ZERO) + row.amount
            else:
                profit += row.amount
        if profit:
            if retained_id is None:
                raise _locked(
                    f"손익을 옮길 {RETAINED} 계정이 없습니다(E-18).", "NO_RETAINED"
                )
            point = (retained_id, None)
            carried[point] = carried.get(point, ZERO) + profit
        made = 0
        for (account_id, partner_id), amount in sorted(
            carried.items(), key=lambda x: (x[0][0], x[0][1] or 0)
        ):
            if not amount:
                continue
            connection.execute(
                text(
                    "INSERT INTO erp.opening_balance (workspace_id, generation_id, "
                    "fiscal_year, account_id, partner_id, side, amount) "
                    "VALUES (:w, :g, :y, :account, :partner, :side, :amount)"
                ),
                {
                    **_s(scoped),
                    "y": nxt,
                    "account": account_id,
                    "partner": partner_id,
                    "side": "DEBIT" if amount > 0 else "CREDIT",
                    "amount": abs(amount),
                },
            )
            made += 1
        return (
            {"fiscalYear": nxt, "created": made, "retained": str(-profit)},
            "opening_balance",
            0,
        )

    body = {"fiscalYear": fiscal_year}
    return _action(context, "erp.opening_balance.carry", key, body, run, 201)


def opening_locked(connection, scoped, fiscal_year: str) -> None:
    """기초 잔액은 그 해 **1월이 열려 있을 때만** 고친다. 마감한 장부의 출발점은 안 바꾼다."""
    if _closed(connection, scoped, f"{fiscal_year}-01"):
        raise _locked(
            f"{fiscal_year}년 1월이 마감돼 있습니다. 해제한 뒤 고치세요.",
            "YEAR_CLOSED",
        )


def check_opening(connection, scoped, merged: dict[str, Any]) -> None:
    """E-35 기초 잔액 저장 전 검사. 기준정보 저장 흐름(service.validate)에서 부른다."""
    opening_locked(connection, scoped, merged["fiscal_year"])
    if Decimal(merged["amount"]) <= 0:
        raise invalid("amount", "금액은 0보다 커야 합니다.")
    account = connection.execute(
        text(
            f"SELECT requires_partner, is_active FROM erp.account WHERE {_S} AND id=:id"
        ),
        {**_s(scoped), "id": merged["account_id"]},
    ).first()
    if account is None or not account.is_active:
        raise invalid("account_id", "사용 중인 계정을 선택하세요.")
    if account.requires_partner and not merged.get("partner_id"):
        raise invalid("partner_id", "이 계정은 거래처가 필요합니다.")
    if (
        merged.get("partner_id")
        and not connection.execute(
            text(f"SELECT 1 FROM erp.partner WHERE {_S} AND id=:id"),
            {**_s(scoped), "id": merged["partner_id"]},
        ).first()
    ):
        raise invalid("partner_id", "현재 공간의 대상을 선택하세요.")
