"""A current DB selection claim remains bounded by original signatures and registrations."""

import base64
import hashlib
import importlib.util
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from test_gw_acceptance_collection import registered_fixture

from fs.common.errors import ApiError
from fs.gw.acceptance_reconciliation import (
    sign_reconciliation,
    verify_registered_sources,
)
from fs.gw.operating_contract import canonical, verify_evidence
from fs.gw.readiness import SOURCE_FIELD


def prepared():
    key, rows, ctx = registered_fixture()
    docs = {
        r["kind"]: {"envelope": r["metrics"][SOURCE_FIELD], "signature": r["signature"]}
        for r in rows
    }
    proof = sign_reconciliation(
        docs,
        signer=key,
        signer_id="runner-1",
        database_observed_at=ctx["now"].isoformat(),
        **ctx,
    )
    return key, rows, ctx, proof


@pytest.mark.parametrize(
    "change",
    [
        "none",
        "context",
        "observation-before",
        "observation-future",
        "observation-naive",
        "observation-broken",
        "registered-after",
        "result",
        "scope",
        "ready",
        "metric",
        "source-run",
        "source-digest",
        "latest-fail",
        "latest-partial",
        "latest-no-original",
        "old-policy",
        "old-version",
        "tamper",
        "missing",
        "wrong-key",
    ],
)
def test_registered_v2_context_and_snapshot_cannot_replace_current_originals(change):
    key, rows, ctx, proof = prepared()
    payload = deepcopy(proof["envelope"])
    diag = payload["metrics"]["acceptanceDiagnostics"]
    if change == "context":
        diag["contextDigest"] = "f" * 64
    elif change == "observation-before":
        diag["observedAt"] = (ctx["now"] - timedelta(seconds=1)).isoformat()
    elif change == "observation-future":
        diag["observedAt"] = (ctx["now"] + timedelta(seconds=1)).isoformat()
    elif change == "observation-naive":
        diag["observedAt"] = "2026-10-18T04:00:00"
    elif change == "observation-broken":
        diag["observedAt"] = "broken"
    elif change == "registered-after":
        rows[0]["recorded_at"] += timedelta(seconds=1)
    elif change == "result":
        payload["result"] = "PASS"
    elif change == "scope":
        diag["scope"] = "LIVE_COMPANY"
    elif change == "ready":
        diag["ready"] = True
    elif change == "metric":
        payload["metrics"]["revocationsReapplied"] = True
    elif change == "source-run":
        diag["backup"]["runId"] = str(uuid4())
    elif change == "source-digest":
        diag["backup"]["sourceDigest"] = "e" * 64
    elif change.startswith("latest-"):
        newer = deepcopy(rows[0])
        newer["id"] += 10
        newer["run_id"] = str(uuid4())
        newer["metrics"][SOURCE_FIELD]["runId"] = newer["run_id"]
        newer["result"] = "FAIL" if change == "latest-fail" else "PARTIAL"
        newer["metrics"][SOURCE_FIELD]["result"] = newer["result"]
        newer["signature"] = base64.b64encode(
            key.sign(canonical(newer["metrics"][SOURCE_FIELD]))
        ).decode()
        if change == "latest-no-original":
            newer["metrics"].pop(SOURCE_FIELD)
        rows.append(newer)
    elif change == "old-policy":
        rows[0]["policy_revision_id"] += 1
    elif change == "old-version":
        rows[0]["code_revision"] = "abc1234"
    elif change == "tamper":
        rows[0]["manifest_digest"] = "c" * 64
    elif change == "missing":
        rows.pop()
    elif change == "wrong-key":
        ctx["public_keys"] = {}
    payload["manifestDigest"] = hashlib.sha256(canonical(diag)).hexdigest()
    signature = base64.b64encode(key.sign(canonical(payload))).decode()
    if change == "none":
        data = verify_evidence(payload, signature, **ctx)
        verify_registered_sources(data, rows, policy_id=1, **ctx)
        assert data.result == "PARTIAL" and diag["version"] == 2
        assert all(
            diag[k] == "UNVERIFIED"
            for k in (
                "externalStorage",
                "journalCoverage",
                "liveCompany",
                "finalRelease",
            )
        )
    else:
        with pytest.raises(ApiError):
            data = verify_evidence(payload, signature, **ctx)
            verify_registered_sources(data, rows, policy_id=1, **ctx)


@pytest.mark.parametrize(
    "extra",
    [
        [],
        ["--context", "ignored"],
        ["--backup", "ignored"],
        ["--restore", "ignored"],
        ["--storage-copy", "ignored"],
    ],
)
def test_cli_current_mode_never_mixes_operator_files_or_unsigned_output(
    tmp_path, monkeypatch, capsys, extra
):
    path = Path(__file__).resolve().parents[2] / "tools/gw_acceptance_collect.py"
    spec = importlib.util.spec_from_file_location("current_cli", path)
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    tmp_path.chmod(0o700)
    args = ["collector", "--current-company-id", "3", "--output", str(tmp_path / "new")]
    if extra:
        args += ["--signed-reconciliation", *extra]
    monkeypatch.setattr("sys.argv", args)
    monkeypatch.setattr(
        cli, "create_engine", lambda *_a, **_k: pytest.fail("must not connect")
    )
    monkeypatch.setattr(cli, "load", lambda *_a: pytest.fail("must not load files"))
    assert cli.main() == 1 and not (tmp_path / "new").exists()
    assert "signature" not in capsys.readouterr().out
