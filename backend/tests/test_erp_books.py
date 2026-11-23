"""DSN-11 1f 장부·결산: 원장·시산표·재무제표의 항등식, 월 마감 자물쇠, 기초 잔액과 연도 이월."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

BASE = "/api/v1/erp"
# 템플릿 시드와 FS_TODAY가 못 박은 기준일(conftest).
TODAY = date(2026, 9, 24)
YEAR_START = TODAY.replace(month=1, day=1).isoformat()


def _headers(data):
    return {"X-CSRF-Token": data["csrfToken"], "Idempotency-Key": uuid4().hex}


def _call(client, data, method, path, body=None):
    return client.request(method, f"{BASE}{path}", json=body, headers=_headers(data))


def _get(client, path):
    return client.get(f"{BASE}{path}").json()["data"]


def _range(date_from: str = YEAR_START, date_to: str | None = None) -> str:
    return f"date_from={date_from}&date_to={date_to or TODAY.isoformat()}"


@pytest.fixture
def erp(guest_space):
    return guest_space[0], guest_space[1]


def _account(client, code):
    return next(
        a for a in _get(client, "/accounts?limit=200") if a["accountCode"] == code
    )


def test_trial_balance_is_balanced_and_opening_balance_counts(erp):
    client, _ = erp
    body = _get(client, f"/trial-balance?{_range()}")
    assert body["balanced"], body["totals"]
    assert Decimal(body["totals"]["debitBalance"]) == Decimal(
        body["totals"]["creditBalance"]
    )
    bank = next(r for r in body["rows"] if r["accountCode"] == "BANK")
    # 시드 기초 잔액 5천만 원이 기초로 잡힌다(E-35).
    assert Decimal(bank["opening"]) == Decimal(50_000_000)


def test_ledger_running_balance_ends_at_the_trial_balance_closing(erp):
    client, _ = erp
    bank = _account(client, "BANK")
    ledger = _get(client, f"/ledger?{_range()}&account_id={bank['id']}")
    rows = _get(client, f"/trial-balance?{_range()}")["rows"]
    closing = next(r for r in rows if r["accountCode"] == "BANK")["closing"]
    assert Decimal(ledger["closing"]) == Decimal(closing)
    running = Decimal(ledger["opening"])
    for line in ledger["lines"]:
        amount = Decimal(line["amount"])
        running += amount if line["side"] == "DEBIT" else -amount
        assert Decimal(line["balance"]) == running


def test_ledger_shows_both_an_entry_and_its_reversal(erp):
    client, data = erp
    entry = _make_entry(client, data)
    assert (
        _call(client, data, "POST", f"/journal-entries/{entry}/confirm").status_code
        == 200
    )
    account = _account(client, "BANK")
    before = _get(client, f"/ledger?{_range()}&account_id={account['id']}")
    assert (
        _call(
            client,
            data,
            "POST",
            f"/journal-entries/{entry}/reverse",
            {"reason": "테스트 정정"},
        ).status_code
        == 200
    )
    after = _get(client, f"/ledger?{_range()}&account_id={account['id']}")
    # 원 전표도 반대 전표도 명세에 남고, 잔액은 제자리로 돌아온다.
    assert len(after["lines"]) == len(before["lines"]) + 1
    assert Decimal(after["closing"]) == Decimal(before["closing"]) - Decimal(10_000)
    assert any(line["status"] == "reversed" for line in after["lines"])


def _make_entry(client, data, amount: str = "10000") -> int:
    bank, sales = _account(client, "BANK"), _account(client, "INTEREST_INCOME")
    made = _call(
        client,
        data,
        "POST",
        "/journal-entries",
        {"entryDate": TODAY.isoformat(), "description": "1f 테스트"},
    )
    assert made.status_code == 201, made.text
    entry_id = made.json()["data"]["id"]
    lines = _call(
        client,
        data,
        "PUT",
        f"/journal-entries/{entry_id}/lines",
        {
            "lines": [
                {"accountId": bank["id"], "side": "DEBIT", "amount": amount},
                {"accountId": sales["id"], "side": "CREDIT", "amount": amount},
            ]
        },
    )
    assert lines.status_code == 200, lines.text
    return entry_id


def test_statements_balance_and_net_income_sits_in_equity(erp):
    client, _ = erp
    body = _get(client, f"/statements?{_range()}")
    assert Decimal(body["difference"]) == 0
    assert Decimal(body["assets"]) == Decimal(body["liabilities"]) + Decimal(
        body["equity"]
    )
    labels = [row["label"] for row in body["balanceSheet"]]
    assert "당기순이익" in labels
    income = {row["label"]: row["amount"] for row in body["incomeStatement"]}
    assert Decimal(income["당기순이익"]) == Decimal(body["netIncome"])


def test_contra_accounts_are_counted_in_the_class_direction(erp):
    """매출환입은 매출(대변) 분류인데 차변 잔액이다. 분류 방향으로 세야 매출에서 빠진다."""
    client, _ = erp
    body = _get(client, f"/statements?{_range()}")
    rows = {row["label"]: row["amount"] for row in body["incomeStatement"]}
    returns = next(
        (value for label, value in rows.items() if "매출환입" in label), None
    )
    assert returns is not None and Decimal(returns) < 0


def test_closed_month_refuses_entries_but_not_the_business(erp):
    client, data = erp
    month = TODAY.strftime("%Y-%m")
    entry = _make_entry(client, data)
    assert _call(client, data, "DELETE", f"/journal-entries/{entry}").status_code == 204
    closed = _call(client, data, "POST", f"/fiscal-periods/{month}/close")
    assert closed.status_code == 200, closed.text
    assert closed.json()["data"]["status"] == "closed"
    blocked = _call(
        client,
        data,
        "POST",
        "/journal-entries",
        {"entryDate": TODAY.isoformat(), "description": "마감 뒤"},
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["details"]["reason"] == "MONTH_CLOSED"
    # 업무는 막지 않는다. 판매계획 확정은 그대로 된다.
    plan = _call(
        client,
        data,
        "POST",
        "/sales-plans",
        {"planCode": "SP-1F", "targetMonth": month},
    )
    assert plan.status_code == 201


def test_a_month_with_drafts_cannot_be_closed(erp):
    client, data = erp
    _make_entry(client, data)
    refused = _call(
        client, data, "POST", f"/fiscal-periods/{TODAY.strftime('%Y-%m')}/close"
    )
    assert refused.status_code == 409
    assert refused.json()["error"]["details"]["reason"] == "DRAFT_ENTRIES"


def test_reopen_only_when_the_next_month_is_open(erp):
    client, data = erp
    first, second = f"{TODAY.year}-01", f"{TODAY.year}-02"
    for month in (first, second):
        assert (
            _call(client, data, "POST", f"/fiscal-periods/{month}/close").status_code
            == 200
        )
    refused = _call(client, data, "POST", f"/fiscal-periods/{first}/reopen")
    assert refused.status_code == 409
    assert refused.json()["error"]["details"]["reason"] == "NEXT_MONTH_CLOSED"
    assert (
        _call(client, data, "POST", f"/fiscal-periods/{second}/reopen").status_code
        == 200
    )
    assert (
        _call(client, data, "POST", f"/fiscal-periods/{first}/reopen").status_code
        == 200
    )


def test_period_list_counts_drafts_and_unposted(erp):
    client, data = erp
    _make_entry(client, data)
    months = _get(client, f"/fiscal-periods?year={TODAY.year}")
    assert len(months) == 12
    now = next(m for m in months if m["periodMonth"] == TODAY.strftime("%Y-%m"))
    assert now["draftCount"] == 1
    assert now["status"] == "open"


def test_opening_balance_needs_an_open_january_and_a_partner_when_required(erp):
    client, data = erp
    year = str(TODAY.year)
    receivable = _account(client, "AR")  # 거래처가 필요한 계정
    missing = _call(
        client,
        data,
        "POST",
        "/opening-balances",
        {
            "fiscalYear": year,
            "accountId": receivable["id"],
            "side": "DEBIT",
            "amount": "1000",
        },
    )
    assert missing.status_code == 400
    assert "partnerId" in missing.json()["error"]["details"]["fields"]
    assert (
        _call(client, data, "POST", f"/fiscal-periods/{year}-01/close").status_code
        == 200
    )
    partner = _get(client, "/partners")[0]
    locked = _call(
        client,
        data,
        "POST",
        "/opening-balances",
        {
            "fiscalYear": year,
            "accountId": receivable["id"],
            "partnerId": partner["id"],
            "side": "DEBIT",
            "amount": "1000",
        },
    )
    assert locked.status_code == 409
    assert locked.json()["error"]["details"]["reason"] == "YEAR_CLOSED"


def test_carry_forward_moves_profit_into_retained_earnings(erp):
    client, data = erp
    year = str(TODAY.year)
    early = _call(
        client, data, "POST", "/opening-balances/carry-forward", {"fiscalYear": year}
    )
    assert early.status_code == 409
    assert early.json()["error"]["details"]["reason"] == "YEAR_NOT_CLOSED"
    assert (
        _call(client, data, "POST", f"/fiscal-periods/{year}-12/close").status_code
        == 200
    )
    made = _call(
        client, data, "POST", "/opening-balances/carry-forward", {"fiscalYear": year}
    )
    assert made.status_code == 201, made.text
    body = made.json()["data"]
    assert body["fiscalYear"] == str(int(year) + 1) and body["created"] > 0
    rows = _get(client, "/opening-balances?limit=200")
    carried = [r for r in rows if r["fiscalYear"] == body["fiscalYear"]]
    assert carried, rows
    # 이월 잔액도 차·대가 맞는다.
    debit = sum(Decimal(r["amount"]) for r in carried if r["side"] == "DEBIT")
    credit = sum(Decimal(r["amount"]) for r in carried if r["side"] == "CREDIT")
    assert debit == credit
    # 손익 계정은 이월하지 않는다.
    accounts = {a["id"]: a for a in _get(client, "/accounts?limit=200")}
    assert all(
        accounts[r["accountId"]]["accountClass"] in ("ASSET", "LIABILITY", "EQUITY")
        for r in carried
    )
    again = _call(
        client, data, "POST", "/opening-balances/carry-forward", {"fiscalYear": year}
    )
    assert again.status_code == 409
    assert again.json()["error"]["details"]["reason"] == "ALREADY_CARRIED"


def test_books_are_scoped_to_the_workspace(erp):
    """다른 공간의 거래처 id로 원장을 보면 빈 장부다(남의 전표가 새지 않는다)."""
    client, _ = erp
    ledger = _get(client, f"/ledger?{_range()}&partner_id=999999")
    assert ledger["lines"] == [] and Decimal(ledger["opening"]) == 0
