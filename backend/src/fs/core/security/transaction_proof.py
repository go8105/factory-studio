"""Optional physical-source transaction evidence; never infer rollback from absence."""

import os

from sqlalchemy import text

from fs.core.backup import BackupError, database_identity


def timeline(c):
    return c.execute(
        text("SELECT substring(pg_walfile_name(pg_current_wal_lsn()),1,8)")
    ).scalar_one()


def capture(c):
    enabled = os.environ.get("FS_GW_JOURNAL_TX_PROOF", "false")
    if enabled == "false":
        return {}
    if enabled != "true" or c.dialect.name != "postgresql":
        raise BackupError("트랜잭션 근거 설정과 PostgreSQL 환경을 확인하세요.")
    return {
        "transactionProof": {
            "version": 1,
            "sourceIdentity": database_identity(c),
            "timeline": timeline(c),
            "transactionId": c.execute(
                text("SELECT pg_current_xact_id()::text")
            ).scalar_one(),
        }
    }


def classify(c, records, confirmed):
    result = {
        r["digest"]: "AUDIT_CONFIRMED" if r["digest"] in confirmed else "UNKNOWN"
        for r in records
    }
    pending = [
        r
        for r in records
        if r["digest"] not in confirmed and r["payload"].get("transactionProof")
    ]
    if not pending:
        return result
    identity = database_identity(c)
    current_timeline = timeline(c)
    # A snapshot xmax can precede a still-active recorded transaction.
    # Allocate the read-only probe ID to bound all IDs assigned before this probe.
    upper_bound = int(c.execute(text("SELECT pg_current_xact_id()::text")).scalar_one())
    eligible = []
    for record in pending:
        proof = record["payload"]["transactionProof"]
        if proof["sourceIdentity"] != identity or proof["timeline"] != current_timeline:
            result[record["digest"]] = "SOURCE_MISMATCH"
        elif int(proof["transactionId"]) < upper_bound:
            eligible.append(record)
    if eligible:
        statuses = {
            row[0]: row[1]
            for row in c.execute(
                text(
                    "SELECT value,pg_xact_status(value::xid8) FROM unnest(CAST(:ids AS text[])) AS t(value)"
                ),
                {
                    "ids": sorted(
                        {
                            r["payload"]["transactionProof"]["transactionId"]
                            for r in eligible
                        }
                    )
                },
            ).tuples()
        }
        for record in eligible:
            status = statuses.get(
                record["payload"]["transactionProof"]["transactionId"]
            )
            result[record["digest"]] = {
                "aborted": "ABORT_CONFIRMED",
                "in progress": "PENDING",
                "committed": "COMMITTED_WITHOUT_AUDIT",
            }.get(status, "UNKNOWN")
    return result


def summary(dispositions):
    counts = {
        kind: sum(v == kind for v in dispositions.values())
        for kind in (
            "AUDIT_CONFIRMED",
            "ABORT_CONFIRMED",
            "PENDING",
            "SOURCE_MISMATCH",
            "COMMITTED_WITHOUT_AUDIT",
            "UNKNOWN",
        )
    }
    settled = counts["AUDIT_CONFIRMED"] + counts["ABORT_CONFIRMED"]
    return {
        "transactionDispositionCounts": counts,
        "settledRecords": settled,
        "allTransactionsSettled": bool(dispositions) and settled == len(dispositions),
        "completenessConfirmed": False,
    }
