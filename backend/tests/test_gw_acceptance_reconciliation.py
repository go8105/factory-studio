"""Limited signed reconciliation must never outlive its latest original proofs."""

import base64
import hashlib
import importlib.util
import json
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from test_gw_acceptance_collection import fixture, registered_fixture, signed
from test_gw_operating_contract import NOW

from fs.common.errors import ApiError
from fs.gw.acceptance_reconciliation import (
    sign_reconciliation,
    verify_registered_sources,
)
from fs.gw.launch_gate import build
from fs.gw.operating_contract import EvidenceEnvelope, canonical, verify_evidence
from fs.gw.readiness import SOURCE_FIELD, assess


def proof_fixture():
    key, rows, ctx = registered_fixture()
    docs = {
        r["kind"]: {"envelope": r["metrics"][SOURCE_FIELD], "signature": r["signature"]}
        for r in rows
    }
    doc = sign_reconciliation(docs, signer=key, signer_id="runner-1", **ctx)
    data = EvidenceEnvelope.model_validate(doc["envelope"])
    row = data.model_dump() | {
        "id": 3,
        "workspace_id": 10,
        "generation_id": 20,
        "policy_revision_id": 1,
        "recorded_at": NOW,
        "started_at": NOW,
        "finished_at": NOW,
        "metrics": data.metrics.model_dump(by_alias=True)
        | {SOURCE_FIELD: doc["envelope"]},
        "signature": doc["signature"],
    }
    return key, rows + [row], ctx, doc


def assessed(rows, ctx):
    return assess(
        rows,
        policy_id=1,
        **{k: v for k, v in ctx.items() if k not in {"workspace_id", "generation_id"}},
    )


@pytest.mark.parametrize("restore_result", ["PASS", "PARTIAL"])
def test_actual_signatures_bind_original_runs_and_keep_all_release_gates_closed(
    restore_result,
):
    key, payloads, ctx = fixture()
    payloads["RESTORE"]["result"] = restore_result
    doc = sign_reconciliation(
        signed(payloads, key), signer=key, signer_id="runner-1", **ctx
    )
    data = verify_evidence(doc["envelope"], doc["signature"], **ctx)
    assert data.result == "PARTIAL"
    assert (
        data.metrics.acceptance_diagnostics.restore.run_id
        == payloads["RESTORE"]["runId"]
    )
    _, rows, ctx, _ = proof_fixture()
    checks = assessed(rows, ctx)
    assert checks[2]["state"] == "PARTIAL" and checks[2]["signatureVerified"]
    gate = build(
        policy=ctx["policy"],
        connected=10,
        enrolled=10,
        departments=1,
        responsible_active=True,
        evidence=checks,
    )
    assert not gate["ready"] and gate["unverifiedCount"] == 4
    assert (
        next(c for c in gate["checks"] if c["code"] == "ACCEPTANCE")["state"]
        == "BLOCKED"
    )


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "fail",
        "partial-backup",
        "manifest",
        "overlap",
        "same-run",
        "stale",
        "synthetic",
        "tamper",
    ],
)
def test_builder_refuses_inadequate_or_unsigned_sources(change):
    key, payloads, ctx = fixture()
    if change == "fail":
        payloads["RESTORE"]["result"] = "FAIL"
    elif change == "partial-backup":
        payloads["BACKUP"]["result"] = "PARTIAL"
    elif change == "manifest":
        payloads["RESTORE"]["manifestDigest"] = "f" * 64
    elif change == "overlap":
        payloads["RESTORE"]["startedAt"] = payloads["BACKUP"]["startedAt"]
        payloads["RESTORE"]["metrics"]["elapsedSeconds"] = 1800
    elif change == "same-run":
        payloads["RESTORE"]["runId"] = payloads["BACKUP"]["runId"]
    elif change == "stale":
        ctx["now"] += timedelta(hours=2)
    docs = signed(payloads, key)
    if change == "missing":
        del docs["RESTORE"]
    elif change == "synthetic":
        docs["RESTORE"] = {
            "kind": "SYNTHETIC_GW_ROUTE_EXECUTION",
            "result": "PARTIAL",
            "ready": False,
        }
    elif change == "tamper":
        docs["RESTORE"]["envelope"]["manifestDigest"] = "f" * 64
    with pytest.raises(ApiError):
        sign_reconciliation(docs, signer=key, signer_id="runner-1", **ctx)


@pytest.mark.parametrize(
    "change",
    [
        "pass",
        "kind",
        "ready",
        "scope",
        "live",
        "extra-metric",
        "digest",
        "same-run",
        "reference-type",
    ],
)
def test_even_trusted_signer_cannot_promote_or_expand_limited_contract(change):
    key, _, ctx, doc = proof_fixture()
    payload = deepcopy(doc["envelope"])
    diagnostic = payload["metrics"]["acceptanceDiagnostics"]
    if change == "pass":
        payload["result"] = "PASS"
    elif change == "kind":
        payload["kind"] = "RESTORE"
    elif change == "ready":
        diagnostic["ready"] = True
    elif change == "scope":
        diagnostic["scope"] = "LIVE_COMPANY"
    elif change == "live":
        diagnostic["liveCompany"] = "CONFIRMED"
    elif change == "extra-metric":
        payload["metrics"]["revocationsReapplied"] = True
    elif change == "same-run":
        diagnostic["restore"]["runId"] = payload["runId"]
    elif change == "reference-type":
        diagnostic["backup"]["runId"] = 10
    payload["manifestDigest"] = hashlib.sha256(canonical(diagnostic)).hexdigest()
    if change == "digest":
        payload["manifestDigest"] = "f" * 64
    signature = base64.b64encode(key.sign(canonical(payload))).decode()
    with pytest.raises(ApiError):
        verify_evidence(payload, signature, **ctx)


@pytest.mark.parametrize(
    "change",
    [
        "new-fail",
        "new-partial",
        "new-pass",
        "missing",
        "legacy",
        "tamper",
        "row-tamper",
        "policy",
        "version",
        "scope",
        "expired",
        "future-source",
    ],
)
def test_latest_sources_revalidated_without_older_success_fallback(change):
    key, rows, ctx, doc = proof_fixture()
    data = verify_evidence(doc["envelope"], doc["signature"], **ctx)
    source = rows[1]
    if change.startswith("new-"):
        newer = deepcopy(source)
        newer["id"] = 4
        newer["run_id"] = str(uuid4())
        newer["result"] = change[4:].upper()
        envelope = newer["metrics"][SOURCE_FIELD]
        envelope["runId"] = newer["run_id"]
        envelope["result"] = newer["result"]
        newer["signature"] = base64.b64encode(key.sign(canonical(envelope))).decode()
        rows.append(
            newer
        )  # Same recorded_at: id must decide, independent of list order.
    elif change == "missing":
        rows.remove(source)
    elif change == "legacy":
        source["metrics"].pop(SOURCE_FIELD)
    elif change == "tamper":
        source["metrics"][SOURCE_FIELD]["manifestDigest"] = "f" * 64
    elif change == "row-tamper":
        source["manifest_digest"] = "f" * 64
    elif change == "policy":
        source["policy_revision_id"] = 2
    elif change == "version":
        source["code_revision"] = "f" * 7
    elif change == "scope":
        source["workspace_id"] = 11
    elif change == "expired":
        ctx["now"] += timedelta(hours=2)
    else:
        source["finished_at"] += timedelta(seconds=1)
    with pytest.raises(ApiError):
        verify_registered_sources(data, rows, policy_id=1, **ctx)
    assert assessed(rows, ctx)[2]["state"] == "INVALID"


def test_cli_signs_private_partial_and_rejects_overwrite_and_wrong_key(
    tmp_path, monkeypatch, capsys
):
    spec = importlib.util.spec_from_file_location(
        "collector",
        Path(__file__).resolve().parents[2] / "tools/gw_acceptance_collect.py",
    )
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    key, payloads, ctx = fixture()
    docs = signed(payloads, key)
    tmp_path.chmod(0o700)
    for name, value in [
        ("backup", docs["BACKUP"]),
        ("restore", docs["RESTORE"]),
        (
            "context",
            {
                "workspaceId": 10,
                "generationId": 20,
                "policy": ctx["policy"].model_dump(by_alias=True),
                "codeRevision": ctx["code_revision"],
                "dbRevision": ctx["db_revision"],
            },
        ),
    ]:
        path = tmp_path / name
        path.write_bytes(canonical(value))
        path.chmod(0o600)
    keyfile = tmp_path / "key"
    keyfile.write_bytes(key.private_bytes_raw())
    keyfile.chmod(0o600)
    monkeypatch.setenv("FS_GW_RUNNER_KEY_FILE", str(keyfile))
    monkeypatch.setenv("FS_GW_RUNNER_KEY_ID", "runner-1")
    monkeypatch.setenv(
        "FS_GW_EVIDENCE_PUBLIC_KEYS",
        json.dumps(
            {"runner-1": base64.b64encode(key.public_key().public_bytes_raw()).decode()}
        ),
    )

    class Clock:
        @staticmethod
        def now(_):
            return NOW

    monkeypatch.setattr(cli, "datetime", Clock)
    args = [
        "collector",
        "--context",
        str(tmp_path / "context"),
        "--backup",
        str(tmp_path / "backup"),
        "--restore",
        str(tmp_path / "restore"),
        "--output",
        str(tmp_path / "output"),
        "--signed-reconciliation",
    ]
    monkeypatch.setattr("sys.argv", args)
    assert cli.main() == 0
    output = tmp_path / "output"
    original = output.read_bytes()
    result = json.loads(original)
    assert (
        verify_evidence(result["envelope"], result["signature"], **ctx).result
        == "PARTIAL"
    )
    assert output.stat().st_mode & 0o777 == 0o600
    assert cli.main() == 1 and output.read_bytes() == original
    output.unlink()
    monkeypatch.setenv("FS_GW_RUNNER_KEY_ID", "unknown")
    assert cli.main() == 1 and not output.exists()
    assert "signature" not in capsys.readouterr().out


@pytest.mark.parametrize(
    "change", ["source-digest", "source-run", "older-acceptance-time"]
)
def test_valid_acceptance_signature_cannot_substitute_original_references(change):
    key, rows, ctx, doc = proof_fixture()
    payload = deepcopy(doc["envelope"])
    diagnostic = payload["metrics"]["acceptanceDiagnostics"]
    if change == "source-digest":
        diagnostic["restore"]["sourceDigest"] = "f" * 64
    elif change == "source-run":
        diagnostic["restore"]["runId"] = str(uuid4())
    else:
        payload["startedAt"] = (NOW - timedelta(seconds=1)).isoformat()
    payload["manifestDigest"] = hashlib.sha256(canonical(diagnostic)).hexdigest()
    signature = base64.b64encode(key.sign(canonical(payload))).decode()
    data = verify_evidence(payload, signature, **ctx)
    with pytest.raises(ApiError):
        verify_registered_sources(data, rows, policy_id=1, **ctx)


def test_future_reconciliation_keeps_clock_warning_even_when_sources_match():
    key, rows, ctx, doc = proof_fixture()
    row = rows[2]
    payload = doc["envelope"] | {
        "finishedAt": (NOW + timedelta(seconds=10)).isoformat()
    }
    row["finished_at"] = NOW + timedelta(seconds=10)
    row["metrics"][SOURCE_FIELD] = payload
    row["signature"] = base64.b64encode(key.sign(canonical(payload))).decode()
    check = assessed(rows, ctx)[2]
    assert check["state"] == "STALE" and "미래" in check["detail"]


@pytest.mark.parametrize("seconds,allowed", [(30, True), (31, False)])
def test_backup_restore_clock_tolerance_is_bounded(seconds, allowed):
    key, payloads, ctx = fixture()
    payloads["RESTORE"]["startedAt"] = (
        datetime.fromisoformat(payloads["BACKUP"]["finishedAt"])
        - timedelta(seconds=seconds)
    ).isoformat()
    payloads["RESTORE"]["finishedAt"] = (
        datetime.fromisoformat(payloads["RESTORE"]["startedAt"])
        + timedelta(seconds=240)
    ).isoformat()
    if allowed:
        assert (
            sign_reconciliation(
                signed(payloads, key), signer=key, signer_id="runner-1", **ctx
            )["envelope"]["result"]
            == "PARTIAL"
        )
    else:
        with pytest.raises(ApiError):
            sign_reconciliation(
                signed(payloads, key), signer=key, signer_id="runner-1", **ctx
            )
