"""Actual PostgreSQL proof: top-level abort, savepoint, pending and source binding."""

# ruff: noqa:F811
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from test_gw_security_transactions import identity  # noqa: F401
from test_security_journal import journal  # noqa: F401

from fs.core.security.journal import append, verified_records, verify
from fs.core.security.recording import record_user
from fs.core.security.transaction_proof import classify, summary
from fs.gw.security_journal import confirmed_digests


def read(journal):
    directory, key = journal
    head = verify(directory, key)["head"]
    return verified_records(directory, key, head, metadata_only=True)[1]


def dispositions(engine, records):
    with engine.execution_options(
        isolation_level="REPEATABLE READ", postgresql_readonly=True
    ).begin() as c:
        return classify(c, records, confirmed_digests(c, records))


def test_actual_abort_pending_savepoint_and_source_mismatch(
    identity, journal, monkeypatch, tmp_path
):
    engine, ctx, _, _ = identity
    monkeypatch.setenv("FS_GW_JOURNAL_TX_PROOF", "true")
    with engine.begin() as c:
        record_user(c, ctx.user_id, "synthetic.committed")
    with pytest.raises(RuntimeError), engine.begin() as c:
        c.execute(
            text("UPDATE core.app_user SET status='disabled' WHERE id=:u"),
            {"u": ctx.user_id},
        )
        record_user(c, ctx.user_id, "synthetic.aborted")
        raise RuntimeError("synthetic rollback")
    with engine.begin() as c:
        nested = c.begin_nested()
        record_user(c, ctx.user_id, "synthetic.savepoint")
        nested.rollback()
    with engine.connect() as pending:
        tx = pending.begin()
        try:
            record_user(pending, ctx.user_id, "synthetic.pending")
            records = read(journal)
            result = dispositions(engine, records)
            by_operation = {
                r["payload"]["operation"]: result[r["digest"]] for r in records
            }
            assert by_operation == {
                "synthetic.committed": "AUDIT_CONFIRMED",
                "synthetic.aborted": "ABORT_CONFIRMED",
                "synthetic.savepoint": "COMMITTED_WITHOUT_AUDIT",
                "synthetic.pending": "PENDING",
            }
        finally:
            tx.rollback()
    records = read(journal)
    result = dispositions(engine, records)
    assert result[records[-1]["digest"]] == "ABORT_CONFIRMED"
    original = dict(records[1]["payload"])
    directory, key = journal
    for overrides in (
        {"sourceIdentity": "f" * 64},
        {"timeline": "FFFFFFFF"},
        {"transactionId": str(2**64 - 1)},
    ):
        append(
            directory,
            key,
            {
                **original,
                "snapshot": {},
                "transactionProof": {**original["transactionProof"], **overrides},
            },
        )
    records = read(journal)
    result = dispositions(engine, records)
    assert [result[r["digest"]] for r in records[-3:]] == [
        "SOURCE_MISMATCH",
        "SOURCE_MISMATCH",
        "UNKNOWN",
    ]
    assert summary(result)["transactionDispositionCounts"]["ABORT_CONFIRMED"] == 2
    assert not summary(result)["allTransactionsSettled"]
    with engine.connect() as c:
        assert (
            c.scalar(
                text("SELECT status FROM core.app_user WHERE id=:u"), {"u": ctx.user_id}
            )
            == "active"
        )


@pytest.mark.parametrize("proof", [True, False])
def test_cli_settled_abort_is_not_committed_or_release_approval(
    identity, journal, monkeypatch, tmp_path, proof
):
    engine, ctx, _, _ = identity
    monkeypatch.setenv("FS_GW_JOURNAL_TX_PROOF", "true" if proof else "false")
    with pytest.raises(RuntimeError), engine.begin() as c:
        record_user(c, ctx.user_id, "synthetic.aborted")
        raise RuntimeError("synthetic rollback")
    directory, key = journal
    root = Path(__file__).resolve().parents[2]
    command = [
        sys.executable,
        str(root / "tools/gw_identity_journal.py"),
        "--expected-head",
        verify(directory, key)["head"],
        "--classify-transactions",
    ]
    report = tmp_path / "review.json"
    tmp_path.chmod(0o700)
    command += ["--review-report", str(report)]
    result = subprocess.run(
        command,
        env={
            **os.environ,
            "PYTHONPATH": str(root / "backend/src"),
            "DATABASE_URL": os.environ["TEST_DATABASE_URL"],
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == (0 if proof else 3)
    output = json.loads(result.stdout)
    assert output["allTransactionsSettled"] == proof
    assert output["settledRecords"] == int(proof)
    assert not output["commitsConfirmed"] and not output["completenessConfirmed"]
    disposition = "ABORT_CONFIRMED" if proof else "UNKNOWN"
    assert output["transactionDispositionCounts"][disposition] == 1
    assert (
        "synthetic.aborted" not in result.stdout
        and "sourceIdentity" not in result.stdout
    )

    review = json.loads(report.read_text())
    assert review["allTransactionsSettled"] == proof
    assert not review["releaseAuthorized"] and not review["checkpointInput"]
    assert review["items"][0]["disposition"] == disposition
    assert "sourceIdentity" not in report.read_text()
