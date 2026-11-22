"""E-30 전표 입력·조회 · E-31 회계 미반영 현황 (DSN-11 F42~F45·F47·F44).

- 일반전표는 손으로 넣는다. 확정 조건은 넷이다: 차변 합 = 대변 합 > 0, 라인 2개 이상,
  계정이 요구하는 관리항목(거래처·부서)이 채워짐, 그 달이 **마감되지 않음**.
- **확정 후에는 고치지 않는다.** 틀렸으면 역분개(REVERSAL) 새 전표를 만들고 원 전표는 `reversed`가
  된다. 지운 것처럼 보이게 만들지 않는다 — 장부는 고친 자국이 남아야 한다.
- 자동 전표는 `posting.py`가 업무 확정과 같은 트랜잭션에서 만든다. 여기서는 조회·역분개만 한다.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import text

from fs.common.scope import read_scope
from fs.erp import posting
from fs.erp.sales import _S, MODULE, _action, _locked, _rows, _s
from fs.erp.service import _read, invalid, not_found

ENTRY_SQL = """
SELECT j.id, j.entry_no, j.entry_date, j.entry_kind, j.source_kind, j.source_id,
       j.source_ref, j.description, j.department_id, j.currency, j.status,
       j.confirmed_at, j.reversal_of_id, d.code department_code,
       o.entry_no reversal_of_no,
       (SELECT x.entry_no FROM erp.journal_entry x WHERE x.workspace_id=j.workspace_id
          AND x.generation_id=j.generation_id AND x.reversal_of_id=j.id) reversed_by_no,
       coalesce((SELECT sum(l.amount) FROM erp.journal_line l
         WHERE l.workspace_id=j.workspace_id AND l.generation_id=j.generation_id
           AND l.journal_entry_id=j.id AND l.side='DEBIT'), 0) debit_total,
       coalesce((SELECT sum(l.amount) FROM erp.journal_line l
         WHERE l.workspace_id=j.workspace_id AND l.generation_id=j.generation_id
           AND l.journal_entry_id=j.id AND l.side='CREDIT'), 0) credit_total
FROM erp.journal_entry j
LEFT JOIN erp.department d ON d.workspace_id=j.workspace_id
 AND d.generation_id=j.generation_id AND d.id=j.department_id
LEFT JOIN erp.journal_entry o ON o.workspace_id=j.workspace_id
 AND o.generation_id=j.generation_id AND o.id=j.reversal_of_id
WHERE j.workspace_id=:w AND j.generation_id=:g"""
LINE_SQL = """
SELECT l.id, l.journal_entry_id, l.line_no, l.account_id, l.side, l.amount,
       l.partner_id, l.department_id, l.project_id, l.memo,
       a.account_code, a.account_name, p.partner_code, d.code department_code,
       j.code project_code
FROM erp.journal_line l
JOIN erp.account a ON a.workspace_id=l.workspace_id AND a.generation_id=l.generation_id
 AND a.id=l.account_id
LEFT JOIN erp.partner p ON p.workspace_id=l.workspace_id
 AND p.generation_id=l.generation_id AND p.id=l.partner_id
LEFT JOIN erp.department d ON d.workspace_id=l.workspace_id
 AND d.generation_id=l.generation_id AND d.id=l.department_id
LEFT JOIN erp.project j ON j.workspace_id=l.workspace_id
 AND j.generation_id=l.generation_id AND j.id=l.project_id
WHERE l.workspace_id=:w AND l.generation_id=:g AND l.journal_entry_id = ANY(:ids)
ORDER BY l.journal_entry_id, l.line_no"""


def _entries(connection, scoped, where: str = "", **params: Any):
    heads = _rows(
        connection,
        ENTRY_SQL + where + " ORDER BY j.entry_date DESC, j.entry_no DESC",
        {**_s(scoped), **params},
    )
    lines = _rows(connection, LINE_SQL, {**_s(scoped), "ids": [h["id"] for h in heads]})
    for head in heads:
        head["lines"] = [x for x in lines if x["journalEntryId"] == head["id"]]
    return heads


def _entry(connection, scoped, entry_id: int, lock: bool = False):
    if lock:
        connection.execute(
            text(f"SELECT id FROM erp.journal_entry WHERE {_S} AND id=:id FOR UPDATE"),
            {**_s(scoped), "id": entry_id},
        )
    found = _entries(connection, scoped, " AND j.id=:id", id=entry_id)
    if not found:
        raise not_found()
    return found[0]


def list_entries(context, month: str | None = None, status: str | None = None):
    where = ""
    params: dict[str, Any] = {}
    if month:
        where += " AND to_char(j.entry_date, 'YYYY-MM')=:month"
        params["month"] = month
    if status:
        where += " AND j.status=:status"
        params["status"] = status
    with _read() as connection:
        return _entries(
            connection, read_scope(connection, context, MODULE), where, **params
        )


def entry_for_source(context, source_kind: str, source_id: int):
    """E-07·E-11 배지: 이 업무의 살아 있는 전표(없으면 왜 없는지)."""
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        found = _entries(
            connection,
            scoped,
            " AND j.source_kind=:kind AND j.source_id=:id AND j.status <> 'reversed'",
            kind=source_kind,
            id=source_id,
        )
        if found:
            return {"entry": found[0], "reason": None}
        if not posting.source_exists(connection, scoped, source_kind, source_id):
            raise not_found()
        waiting = [
            p
            for p in posting.pending(connection, scoped)
            if p["sourceKind"] == source_kind and p["sourceId"] == source_id
        ]
        return {
            "entry": None,
            "reason": waiting[0]["reason"] if waiting else None,
            "reasonText": waiting[0]["reasonText"] if waiting else "",
        }


def _draft(connection, scoped, entry_id: int):
    entry = _entry(connection, scoped, entry_id, lock=True)
    if entry["status"] != "draft":
        raise _locked("작성 중인 전표만 고칠 수 있습니다.", "ENTRY_LOCKED")
    return entry


def _open_month(connection, scoped, entry_date) -> None:
    if posting.month_closed(connection, scoped, entry_date):
        raise _locked("마감한 달에는 전표를 넣을 수 없습니다.", posting.MONTH_CLOSED)


def create_entry(context, values: dict[str, Any], key: str):
    def run(connection, scoped):
        _open_month(connection, scoped, values["entry_date"])
        entry_id = posting.write_entry(
            connection,
            scoped,
            entry_kind="GENERAL",
            entry_date=values["entry_date"],
            lines=[],
            description=values.get("description"),
            department_id=values.get("department_id"),
            status="draft",
        )
        return _entry(connection, scoped, entry_id), "journal_entry", entry_id

    return _action(context, "erp.journal_entry.create", key, values, run, 201)


def set_lines(context, entry_id: int, lines: list[dict], key: str):
    def run(connection, scoped):
        _draft(connection, scoped, entry_id)
        accounts = {
            r.id: r
            for r in connection.execute(
                text(
                    "SELECT id, account_code, is_active, requires_partner, "
                    f"requires_department FROM erp.account WHERE {_S}"
                ),
                _s(scoped),
            )
        }
        rows = []
        for n, line in enumerate(lines, 1):
            where = f"{n}번째 라인: "
            account = accounts.get(line["account_id"])
            if account is None or not account.is_active:
                raise invalid("lines", where + "사용 중인 계정을 선택하세요.")
            if Decimal(line["amount"]) <= 0:
                raise invalid("lines", where + "금액은 0보다 커야 합니다.")
            if account.requires_partner and not line.get("partner_id"):
                raise invalid(
                    "lines", where + f"{account.account_code}는 거래처가 필요합니다."
                )
            if account.requires_department and not line.get("department_id"):
                raise invalid(
                    "lines", where + f"{account.account_code}는 부서가 필요합니다."
                )
            rows.append(line)
        connection.execute(
            text(f"DELETE FROM erp.journal_line WHERE {_S} AND journal_entry_id=:id"),
            {**_s(scoped), "id": entry_id},
        )
        for n, row in enumerate(rows, 1):
            connection.execute(
                text(
                    "INSERT INTO erp.journal_line (workspace_id, generation_id, "
                    "journal_entry_id, line_no, account_id, side, amount, partner_id, "
                    "department_id, project_id, memo) VALUES (:w, :g, :entry, :n, "
                    ":account_id, :side, :amount, :partner_id, :department_id, "
                    ":project_id, :memo)"
                ),
                {
                    **_s(scoped),
                    "partner_id": None,
                    "department_id": None,
                    "project_id": None,
                    "memo": None,
                    **row,
                    "entry": entry_id,
                    "n": n,
                },
            )
        return _entry(connection, scoped, entry_id), "journal_entry", entry_id

    body = {"id": entry_id, "lines": lines}
    return _action(context, "erp.journal_entry.lines", key, body, run)


def confirm_entry(context, entry_id: int, key: str):
    def run(connection, scoped):
        entry = _draft(connection, scoped, entry_id)
        _open_month(connection, scoped, entry["entryDate"])
        if len(entry["lines"]) < 2:
            raise _locked("전표는 라인이 둘 이상이어야 합니다.", "TOO_FEW_LINES")
        debit, credit = Decimal(entry["debitTotal"]), Decimal(entry["creditTotal"])
        if debit != credit:
            raise _locked(
                "차변 합과 대변 합이 다릅니다.",
                "NOT_BALANCED",
                debit=str(debit),
                credit=str(credit),
            )
        if debit <= 0:
            raise _locked("금액이 0인 전표는 확정할 수 없습니다.", "ZERO_AMOUNT")
        connection.execute(
            text(
                "UPDATE erp.journal_entry SET status='confirmed', "
                f"confirmed_at=clock_timestamp() WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": entry_id},
        )
        return _entry(connection, scoped, entry_id), "journal_entry", entry_id

    return _action(context, "erp.journal_entry.confirm", key, {"id": entry_id}, run)


def reverse_entry(context, entry_id: int, reason: str, key: str):
    """정정은 지우기가 아니라 반대 전표다. 원 전표는 `reversed`로 남는다."""

    def run(connection, scoped):
        entry = _entry(connection, scoped, entry_id, lock=True)
        if entry["status"] != "confirmed":
            raise _locked("확정한 전표만 역분개할 수 있습니다.", "NOT_CONFIRMED")
        _open_month(connection, scoped, entry["entryDate"])
        flipped = [
            {
                "account_id": line["accountId"],
                "side": "CREDIT" if line["side"] == "DEBIT" else "DEBIT",
                "amount": Decimal(line["amount"]),
                "partner_id": line["partnerId"],
                "department_id": line["departmentId"],
                "project_id": line["projectId"],
                "memo": line["memo"],
            }
            for line in entry["lines"]
        ]
        new_id = posting.write_entry(
            connection,
            scoped,
            entry_kind="REVERSAL",
            entry_date=entry["entryDate"],
            lines=flipped,
            description=f"{entry['entryNo']} 역분개: {reason}",
            department_id=entry["departmentId"],
            reversal_of_id=entry_id,
        )
        connection.execute(
            text(
                f"UPDATE erp.journal_entry SET status='reversed' WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": entry_id},
        )
        return _entry(connection, scoped, new_id), "journal_entry", new_id

    body = {"id": entry_id, "reason": reason}
    return _action(context, "erp.journal_entry.reverse", key, body, run)


def delete_entry(context, entry_id: int, key: str) -> None:
    def run(connection, scoped):
        _draft(connection, scoped, entry_id)
        for sql in (
            f"DELETE FROM erp.journal_line WHERE {_S} AND journal_entry_id=:id",
            f"DELETE FROM erp.journal_entry WHERE {_S} AND id=:id",
        ):
            connection.execute(text(sql), {**_s(scoped), "id": entry_id})
        return {}, "journal_entry", entry_id

    _action(context, "erp.journal_entry.delete", key, {"id": entry_id}, run, 204)


# ---- E-31 회계 미반영 현황 ----
def list_pending(context):
    with _read() as connection:
        return posting.pending(connection, read_scope(connection, context, MODULE))


def post_pending(context, targets: list[dict], key: str):
    """고른 미반영 업무를 전표로 만든다. 만들 수 없는 것은 이유를 돌려주고 건너뛴다."""

    def run(connection, scoped):
        results = []
        for target in targets:
            source = posting.BY_KEY.get(
                f"{target['source_kind']}:{target['entry_kind']}"
            )
            if source is None:
                raise invalid("targets", "알 수 없는 원천입니다.")
            reason = posting.post(connection, scoped, source, target["source_id"])
            results.append(
                {
                    "sourceKind": target["source_kind"],
                    "entryKind": target["entry_kind"],
                    "sourceId": target["source_id"],
                    "posted": reason is None,
                    "reason": reason,
                    "reasonText": posting.REASONS.get(reason, "") if reason else "",
                }
            )
        done = sum(1 for r in results if r["posted"])
        return (
            {"posted": done, "skipped": len(results) - done, "results": results},
            "journal_entry",
            0,
        )

    return _action(context, "erp.journal_entry.post_pending", key, targets, run)
