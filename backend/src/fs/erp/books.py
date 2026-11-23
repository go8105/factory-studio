"""E-32 원장 · E-33 일계표·월계표·시산표 · E-34 재무제표 (DSN-11 F51~F56).

세 화면 모두 **조회 계산**이다. 장부는 저장하지 않는다 — 확정 전표와 기초 잔액에서 그때그때 센다.
저장하면 전표와 장부가 어긋나고, 어긋난 장부는 아무도 고치지 못한다.

세는 규칙은 하나다.
- **장부에 드는 전표**는 `confirmed`와 `reversed` 둘이다. 역분개한 원 전표(`reversed`)도 남는다 —
  반대 전표가 짝으로 들어와 서로 상쇄된다. 지운 것처럼 보이게 만들지 않는다.
- 모든 금액은 **차변 양수**(debit-positive)로 센다. 표시할 때만 방향을 입힌다:
  원장은 계정의 정상 잔액 방향, 재무제표는 **계정 분류의 방향**이다. 둘은 다르다 —
  감가상각누계액은 자산(차변)인데 정상 잔액이 대변이고, 매출환입은 매출(대변)인데 차변이다.
  분류 방향으로 세야 누계액이 유형자산에서 빠지고 환입이 매출에서 빠진다.
- 기간 시작 **이전**의 움직임은 회계연도 1월 1일부터만 센다. 그 앞은 기초 잔액(E-35)이 책임진다.
  연도가 넘어간 전표는 이월(F58)을 해야 잡힌다. 이월하지 않은 전년 전표는 올해 장부에 없다.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from fs.common.scope import read_scope
from fs.erp.sales import MODULE, _rows, _s
from fs.erp.service import _read

ZERO = Decimal(0)
# 계정 분류의 방향. 재무제표는 계정의 정상 잔액이 아니라 이 방향으로 센다.
CLASS_SIDE = {
    "ASSET": "DEBIT",
    "LIABILITY": "CREDIT",
    "EQUITY": "CREDIT",
    "REVENUE": "CREDIT",
    "COGS": "DEBIT",
    "MFG_COST": "DEBIT",
    "EXPENSE": "DEBIT",
    "NON_OPERATING": "CREDIT",
}
CLASS_LABEL = {
    "ASSET": "자산",
    "LIABILITY": "부채",
    "EQUITY": "자본",
    "REVENUE": "매출액",
    "COGS": "매출원가",
    "MFG_COST": "제조원가",
    "EXPENSE": "판매비와관리비",
    "NON_OPERATING": "영업외손익",
}
POSTED = "j.status IN ('confirmed', 'reversed')"
_JOIN = f"""
FROM erp.journal_line l
JOIN erp.journal_entry j ON j.workspace_id=l.workspace_id
 AND j.generation_id=l.generation_id AND j.id=l.journal_entry_id AND {POSTED}
WHERE l.workspace_id=:w AND l.generation_id=:g
  AND j.entry_date >= :year_start AND j.entry_date <= :date_to"""
# 기간 앞(기초로 접히는 몫)과 기간 안을 한 번에 센다.
_BUCKETS = """
  sum(CASE WHEN j.entry_date < :date_from AND l.side='DEBIT' THEN l.amount ELSE 0 END) before_debit,
  sum(CASE WHEN j.entry_date < :date_from AND l.side='CREDIT' THEN l.amount ELSE 0 END) before_credit,
  sum(CASE WHEN j.entry_date >= :date_from AND l.side='DEBIT' THEN l.amount ELSE 0 END) debit,
  sum(CASE WHEN j.entry_date >= :date_from AND l.side='CREDIT' THEN l.amount ELSE 0 END) credit"""

ACCOUNT_SQL = f"""
WITH ob AS (
  SELECT o.account_id,
         sum(CASE WHEN o.side='DEBIT' THEN o.amount ELSE 0 END) ob_debit,
         sum(CASE WHEN o.side='CREDIT' THEN o.amount ELSE 0 END) ob_credit
  FROM erp.opening_balance o
  WHERE o.workspace_id=:w AND o.generation_id=:g AND o.fiscal_year=:year
  GROUP BY o.account_id
), mv AS (
  SELECT l.account_id, {_BUCKETS}
  {_JOIN}
  GROUP BY l.account_id
)
SELECT a.id account_id, a.account_code, a.account_name, a.account_class,
       a.normal_side, a.statement_group,
       coalesce(ob.ob_debit, 0) + coalesce(mv.before_debit, 0) opening_debit,
       coalesce(ob.ob_credit, 0) + coalesce(mv.before_credit, 0) opening_credit,
       coalesce(mv.debit, 0) debit, coalesce(mv.credit, 0) credit
FROM erp.account a
LEFT JOIN ob ON ob.account_id=a.id
LEFT JOIN mv ON mv.account_id=a.id
WHERE a.workspace_id=:w AND a.generation_id=:g
ORDER BY a.account_code"""

PARTNER_SQL = f"""
WITH ob AS (
  SELECT o.partner_id,
         sum(CASE WHEN o.side='DEBIT' THEN o.amount ELSE 0 END) ob_debit,
         sum(CASE WHEN o.side='CREDIT' THEN o.amount ELSE 0 END) ob_credit
  FROM erp.opening_balance o
  WHERE o.workspace_id=:w AND o.generation_id=:g AND o.fiscal_year=:year
    AND o.partner_id IS NOT NULL
  GROUP BY o.partner_id
), mv AS (
  SELECT l.partner_id, {_BUCKETS}
  {_JOIN} AND l.partner_id IS NOT NULL
  GROUP BY l.partner_id
)
SELECT p.id partner_id, p.partner_code, p.partner_name,
       coalesce(ob.ob_debit, 0) + coalesce(mv.before_debit, 0) opening_debit,
       coalesce(ob.ob_credit, 0) + coalesce(mv.before_credit, 0) opening_credit,
       coalesce(mv.debit, 0) debit, coalesce(mv.credit, 0) credit
FROM erp.partner p
LEFT JOIN ob ON ob.partner_id=p.id
LEFT JOIN mv ON mv.partner_id=p.id
WHERE p.workspace_id=:w AND p.generation_id=:g
ORDER BY p.partner_code"""

LINE_SQL = f"""
SELECT l.id, j.entry_date, j.entry_no, j.entry_kind, j.description, j.status,
       l.side, l.amount, l.memo, l.account_id, l.partner_id,
       a.account_code, a.account_name, a.normal_side,
       p.partner_code, p.partner_name, d.code department_code
FROM erp.journal_line l
JOIN erp.journal_entry j ON j.workspace_id=l.workspace_id
 AND j.generation_id=l.generation_id AND j.id=l.journal_entry_id AND {POSTED}
JOIN erp.account a ON a.workspace_id=l.workspace_id AND a.generation_id=l.generation_id
 AND a.id=l.account_id
LEFT JOIN erp.partner p ON p.workspace_id=l.workspace_id
 AND p.generation_id=l.generation_id AND p.id=l.partner_id
LEFT JOIN erp.department d ON d.workspace_id=l.workspace_id
 AND d.generation_id=l.generation_id AND d.id=l.department_id
WHERE l.workspace_id=:w AND l.generation_id=:g
  AND j.entry_date BETWEEN :date_from AND :date_to
  AND (CAST(:account_id AS bigint) IS NULL OR l.account_id=CAST(:account_id AS bigint))
  AND (CAST(:partner_id AS bigint) IS NULL OR l.partner_id=CAST(:partner_id AS bigint))
ORDER BY j.entry_date, j.entry_no, l.line_no"""

# 기간 앞의 잔액(차변 양수). 기초 잔액 + 회계연도 시작부터 기간 직전까지.
OPENING_SQL = f"""
SELECT
 (SELECT coalesce(sum(CASE WHEN o.side='DEBIT' THEN o.amount ELSE -o.amount END), 0)
  FROM erp.opening_balance o
  WHERE o.workspace_id=:w AND o.generation_id=:g AND o.fiscal_year=:year
    AND (CAST(:account_id AS bigint) IS NULL OR o.account_id=CAST(:account_id AS bigint))
    AND (CAST(:partner_id AS bigint) IS NULL OR o.partner_id=CAST(:partner_id AS bigint)))
 +
 (SELECT coalesce(sum(CASE WHEN l.side='DEBIT' THEN l.amount ELSE -l.amount END), 0)
  FROM erp.journal_line l
  JOIN erp.journal_entry j ON j.workspace_id=l.workspace_id
   AND j.generation_id=l.generation_id AND j.id=l.journal_entry_id AND {POSTED}
  WHERE l.workspace_id=:w AND l.generation_id=:g
    AND j.entry_date >= :year_start AND j.entry_date < :date_from
    AND (CAST(:account_id AS bigint) IS NULL OR l.account_id=CAST(:account_id AS bigint))
    AND (CAST(:partner_id AS bigint) IS NULL OR l.partner_id=CAST(:partner_id AS bigint)))
 AS opening"""


def _range(date_from: date, date_to: date) -> dict[str, Any]:
    """회계연도는 **시작일 기준**이다. 해를 걸친 조회는 시작일의 연도로 본다."""
    return {
        "year": f"{date_from.year:04d}",
        "year_start": date(date_from.year, 1, 1),
        "date_from": date_from,
        "date_to": date_to,
    }


def _d(value) -> Decimal:
    return Decimal(value or 0)


def _balances(row: dict[str, Any]) -> dict[str, Any]:
    """차변 양수로 기초·차·대·기말을 맞춘다."""
    opening = _d(row.pop("openingDebit")) - _d(row.pop("openingCredit"))
    debit, credit = _d(row["debit"]), _d(row["credit"])
    return {
        **row,
        "opening": str(opening),
        "debit": str(debit),
        "credit": str(credit),
        "closing": str(opening + debit - credit),
    }


def _moved(row: dict[str, Any]) -> bool:
    return any(_d(row[k]) for k in ("opening", "debit", "credit", "closing"))


def _accounts(connection, scoped, date_from: date, date_to: date) -> list[dict]:
    rows = [
        _balances(r)
        for r in _rows(
            connection, ACCOUNT_SQL, {**_s(scoped), **_range(date_from, date_to)}
        )
    ]
    return [r for r in rows if _moved(r)]


def trial_balance(context, date_from: date, date_to: date):
    """E-33. 하루면 일계표, 한 달이면 월계표, 기간이면 합계잔액시산표 — 계산은 하나다."""
    with _read() as connection:
        rows = _accounts(
            connection, read_scope(connection, context, MODULE), date_from, date_to
        )
    totals = {
        "opening": ZERO,
        "debit": ZERO,
        "credit": ZERO,
        "debitBalance": ZERO,
        "creditBalance": ZERO,
    }
    for row in rows:
        closing = _d(row["closing"])
        row["debitBalance"] = str(max(closing, ZERO))
        row["creditBalance"] = str(max(-closing, ZERO))
        for key in ("opening", "debit", "credit", "debitBalance", "creditBalance"):
            totals[key] += _d(row[key])
    return {
        "rows": rows,
        "totals": {k: str(v) for k, v in totals.items()},
        # 차대가 어긋나면 장부가 아니라 전표가 깨진 것이다. 숨기지 않고 화면에 띄운다.
        "balanced": totals["debit"] == totals["credit"]
        and totals["debitBalance"] == totals["creditBalance"],
    }


def partner_balances(context, date_from: date, date_to: date):
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        rows = [
            _balances(r)
            for r in _rows(
                connection, PARTNER_SQL, {**_s(scoped), **_range(date_from, date_to)}
            )
        ]
    return [r for r in rows if _moved(r)]


def ledger(
    context,
    date_from: date,
    date_to: date,
    account_id: int | None = None,
    partner_id: int | None = None,
):
    """E-32. 한 계정 또는 한 거래처의 명세와 누계 잔액. 잔액은 차변 양수로 돌려준다."""
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        params = {
            **_s(scoped),
            **_range(date_from, date_to),
            "account_id": account_id,
            "partner_id": partner_id,
        }
        opening = _d(connection.execute(text(OPENING_SQL), params).scalar_one())
        lines = _rows(connection, LINE_SQL, params)
    balance = opening
    for line in lines:
        amount = _d(line["amount"])
        balance += amount if line["side"] == "DEBIT" else -amount
        line["balance"] = str(balance)
    return {
        "opening": str(opening),
        "lines": lines,
        "closing": str(balance),
        "debit": str(
            sum((_d(x["amount"]) for x in lines if x["side"] == "DEBIT"), ZERO)
        ),
        "credit": str(
            sum((_d(x["amount"]) for x in lines if x["side"] == "CREDIT"), ZERO)
        ),
    }


# ---- E-34 재무제표 ----
def _tree(items: list[dict], key: str, title: str) -> list[dict]:
    """대분류 → 표시 구분 → 계정. 화면은 level만 보고 들여쓴다."""
    total = sum((x[key] for x in items), ZERO)
    rows = [{"level": 0, "label": title, "amount": str(total)}]
    groups: dict[str, list[dict]] = {}
    for item in items:
        groups.setdefault(item["statementGroup"] or title, []).append(item)
    # 구분이 하나뿐이고 이름도 대분류와 같으면 같은 줄을 두 번 쓰지 않는다.
    single = len(groups) == 1 and title in groups
    for group, members in groups.items():
        if not single:
            rows.append(
                {
                    "level": 1,
                    "label": group,
                    "amount": str(sum((x[key] for x in members), ZERO)),
                }
            )
        rows += [
            {
                "level": 1 if single else 2,
                "label": f"{x['accountCode']} {x['accountName']}".strip(),
                "amount": str(x[key]),
            }
            for x in members
        ]
    return rows


def statements(context, date_from: date, date_to: date):
    """F55·F56. 같은 계정 집계 하나에서 재무상태표·손익계산서·제조원가명세서를 본다.

    재무상태표는 **기말 잔액**, 손익계산서·제조원가명세서는 **기간 발생액**이다.
    금액은 계정 분류의 방향으로 센다 — 그래야 감가상각누계액이 자산에서 빠진다.
    """
    with _read() as connection:
        rows = _accounts(
            connection, read_scope(connection, context, MODULE), date_from, date_to
        )
    priced = [
        {
            **row,
            "balance": _d(row["closing"])
            * (1 if CLASS_SIDE[row["accountClass"]] == "DEBIT" else -1),
            "period": (_d(row["debit"]) - _d(row["credit"]))
            * (1 if CLASS_SIDE[row["accountClass"]] == "DEBIT" else -1),
        }
        for row in rows
    ]

    def pick(*classes: str) -> list[dict]:
        return [x for x in priced if x["accountClass"] in classes]

    def amount(items: list[dict], key: str) -> Decimal:
        return sum((x[key] for x in items), ZERO)

    revenue = amount(pick("REVENUE"), "period")
    cogs = amount(pick("COGS"), "period")
    manufacturing = amount(pick("MFG_COST"), "period")
    expense = amount(pick("EXPENSE"), "period")
    non_operating = amount(pick("NON_OPERATING"), "period")
    gross = revenue - cogs - manufacturing
    operating = gross - expense
    net = operating + non_operating
    # 당기순이익은 계정이 아니라 결과다. 자본에 얹어야 재무상태표가 맞는다.
    equity = pick("EQUITY") + [
        {
            "accountCode": "",
            "accountName": "당기순이익",
            "statementGroup": "자본",
            "balance": net,
        }
    ]
    assets, liabilities = (
        amount(pick("ASSET"), "balance"),
        amount(pick("LIABILITY"), "balance"),
    )
    capital = amount(equity, "balance")
    income = _tree(pick("REVENUE"), "period", "매출액")
    income += _tree(pick("COGS", "MFG_COST"), "period", "매출원가")
    income.append(
        {"level": 0, "label": "매출총이익", "amount": str(gross), "subtotal": True}
    )
    income += _tree(pick("EXPENSE"), "period", "판매비와관리비")
    income.append(
        {"level": 0, "label": "영업이익", "amount": str(operating), "subtotal": True}
    )
    income += _tree(pick("NON_OPERATING"), "period", "영업외손익")
    income.append(
        {"level": 0, "label": "당기순이익", "amount": str(net), "subtotal": True}
    )
    return {
        "balanceSheet": _tree(pick("ASSET"), "balance", "자산")
        + _tree(pick("LIABILITY"), "balance", "부채")
        + _tree(equity, "balance", "자본"),
        "incomeStatement": income,
        "manufacturingCost": _tree(pick("MFG_COST"), "period", "당기총제조비용"),
        "assets": str(assets),
        "liabilities": str(liabilities),
        "equity": str(capital),
        "netIncome": str(net),
        # 자산 − (부채 + 자본 + 당기순이익). 0이 아니면 전표가 깨진 것이다.
        "difference": str(assets - liabilities - capital),
    }
