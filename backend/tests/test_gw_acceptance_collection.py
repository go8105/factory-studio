import base64
from copy import deepcopy
from datetime import timedelta
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from test_gw_operating_contract import NOW, envelope, policy

from fs.gw.acceptance_collection import collect
from fs.gw.operating_contract import canonical


def fixture():
    key = Ed25519PrivateKey.generate()
    backup = envelope()
    backup["finishedAt"] = (NOW - timedelta(minutes=5)).isoformat()
    backup["metrics"]["storageConfirmedAt"] = backup["finishedAt"]
    restore = backup | {
        "runId": str(uuid4()),
        "kind": "RESTORE",
        "startedAt": (NOW - timedelta(minutes=4)).isoformat(),
        "finishedAt": NOW.isoformat(),
        "metrics": {
            "rowHashesMatch": True,
            "foreignKeysValid": True,
            "sessionsInvalidated": True,
            "revocationsReapplied": True,
            "twoAccountChecks": True,
            "lossWindowSeconds": 60,
            "elapsedSeconds": 240,
        },
    }
    context = {
        "public_keys": {"runner-1": key.public_key().public_bytes_raw()},
        "workspace_id": 10,
        "generation_id": 20,
        "policy": policy(),
        "code_revision": "c4184e1",
        "db_revision": "gw_readiness",
        "now": NOW,
    }
    return key, {"BACKUP": backup, "RESTORE": restore}, context


def signed(payloads, key):
    return {
        kind: {
            "envelope": p,
            "signature": base64.b64encode(key.sign(canonical(p))).decode(),
        }
        for kind, p in payloads.items()
    }


def test_matching_pair_is_only_partial_and_never_a_release_proof():
    key, payloads, ctx = fixture()
    result = collect(signed(payloads, key), **ctx)
    assert result["backupRestorePairVerified"] is True
    assert result["result"] == "PARTIAL"
    assert result["ready"] is False
    assert len(result["remainingConditions"]) == 4


@pytest.mark.parametrize(
    "change", ["manifest", "overlap", "same-run", "partial", "future", "stale"]
)
def test_signed_but_inadequate_pairs_are_blocked(change):
    key, payloads, ctx = fixture()
    b, r = payloads["BACKUP"], payloads["RESTORE"]
    if change == "manifest":
        r["manifestDigest"] = "f" * 64
    elif change == "overlap":
        r["startedAt"] = (NOW - timedelta(minutes=6)).isoformat()
        r["metrics"]["elapsedSeconds"] = 360
    elif change == "same-run":
        r["runId"] = b["runId"]
    elif change == "partial":
        r["result"] = "PARTIAL"
    elif change == "future":
        r["finishedAt"] = (NOW + timedelta(seconds=10)).isoformat()
        r["metrics"]["elapsedSeconds"] = 250
    else:
        b["startedAt"] = b["metrics"]["snapshotStartedAt"] = (
            NOW - timedelta(hours=2)
        ).isoformat()
    report = collect(signed(payloads, key), **ctx)
    assert not report["backupRestorePairVerified"]
    assert report["result"] == "BLOCKED"


@pytest.mark.parametrize(
    "change", ["tamper", "company", "policy", "version", "missing", "extra"]
)
def test_invalid_or_missing_inputs_cannot_supply_acceptance(change):
    key, payloads, ctx = fixture()
    documents = signed(payloads, key)
    if change == "tamper":
        documents["RESTORE"]["envelope"] = deepcopy(payloads["RESTORE"]) | {
            "manifestDigest": "f" * 64
        }
    elif change == "company":
        ctx["workspace_id"] = 11
    elif change == "policy":
        ctx["policy"] = policy(expectedPeople=11)
    elif change == "version":
        ctx["code_revision"] = "fffffff"
    elif change == "missing":
        del documents["RESTORE"]
    else:
        documents["RESTORE"]["ready"] = True
    assert collect(documents, **ctx)["result"] == "BLOCKED"


def test_cli_writes_private_blocked_report_and_refuses_overwrite(
    tmp_path, monkeypatch, capsys
):
    import importlib.util
    import json
    import sys
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "gw_acceptance_collect",
        Path(__file__).resolve().parents[2] / "tools/gw_acceptance_collect.py",
    )
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    key, payloads, ctx = fixture()
    # A real clock makes these historical fixture proofs stale: never promote them.
    documents = signed(payloads, key)
    context = {
        "workspaceId": 10,
        "generationId": 20,
        "policy": policy().model_dump(by_alias=True),
        "codeRevision": ctx["code_revision"],
        "dbRevision": ctx["db_revision"],
    }
    tmp_path.chmod(0o700)
    for name, data in (
        ("context", context),
        ("backup", documents["BACKUP"]),
        ("restore", documents["RESTORE"]),
    ):
        path = tmp_path / name
        path.write_text(json.dumps(data))
        path.chmod(0o600)
    output = tmp_path / "report"
    monkeypatch.setenv(
        "FS_GW_EVIDENCE_PUBLIC_KEYS",
        json.dumps(
            {"runner-1": base64.b64encode(key.public_key().public_bytes_raw()).decode()}
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "collector",
            "--context",
            str(tmp_path / "context"),
            "--backup",
            str(tmp_path / "backup"),
            "--restore",
            str(tmp_path / "restore"),
            "--output",
            str(output),
        ],
    )
    assert cli.main() == 2
    original = output.read_bytes()
    assert output.stat().st_mode & 0o777 == 0o600
    assert json.loads(original)["ready"] is False
    assert cli.main() == 1
    assert output.read_bytes() == original
    assert "signature" not in capsys.readouterr().out
    output.unlink()
    (tmp_path / "context").chmod(0o644)
    assert cli.main() == 1
    assert not output.exists()


def registered_fixture():
    from fs.gw.operating_contract import EvidenceEnvelope
    from fs.gw.readiness import SOURCE_FIELD

    key, payloads, context = fixture()
    documents = signed(payloads, key)
    rows = []
    for id, (kind, doc) in enumerate(documents.items(), 1):
        data = EvidenceEnvelope.model_validate(doc["envelope"])
        row = data.model_dump()
        row.update(
            id=id,
            workspace_id=10,
            generation_id=20,
            policy_revision_id=1,
            recorded_at=NOW,
            started_at=NOW.fromisoformat(data.started_at),
            finished_at=NOW.fromisoformat(data.finished_at),
            metrics=data.metrics.model_dump(by_alias=True)
            | {SOURCE_FIELD: doc["envelope"]},
            signature=doc["signature"],
        )
        rows.append(row)
    return key, rows, context


def test_registered_pair_revalidates_stored_rows_and_preserves_no_release_boundary():
    from fs.gw.acceptance_collection import collect_registered

    _, rows, ctx = registered_fixture()
    result = collect_registered(rows, policy_id=1, **ctx)
    assert result["result"] == "PARTIAL"
    assert result["source"] == "LATEST_REGISTRATIONS"
    assert all(r["state"] == "RECORDED_PASS" for r in result["registrations"])
    assert not result["ready"]


@pytest.mark.parametrize(
    "change", ["failure", "tamper", "policy", "legacy", "scope", "partial"]
)
def test_latest_registration_never_falls_back_to_older_success(change):
    from fs.gw.acceptance_collection import collect_registered
    from fs.gw.operating_contract import EvidenceEnvelope
    from fs.gw.readiness import SOURCE_FIELD

    key, rows, ctx = registered_fixture()
    newer = deepcopy(rows[1])
    newer["id"] = 3  # Same registration timestamp: greater ID is latest.
    if change in {"failure", "partial"}:
        payload = newer["metrics"][SOURCE_FIELD]
        payload["runId"] = str(uuid4())
        payload["result"] = "FAIL" if change == "failure" else "PARTIAL"
        newer.update(run_id=payload["runId"], result=payload["result"])
        newer["signature"] = base64.b64encode(key.sign(canonical(payload))).decode()
        newer["metrics"] = EvidenceEnvelope.model_validate(payload).metrics.model_dump(
            by_alias=True
        ) | {SOURCE_FIELD: payload}
    elif change == "tamper":
        newer["manifest_digest"] = "f" * 64
    elif change == "policy":
        newer["policy_revision_id"] = 2
    elif change == "scope":
        newer["workspace_id"] = 11
    else:
        newer["metrics"] = {}
    report = collect_registered([newer, *rows], policy_id=1, **ctx)
    assert report["result"] == "BLOCKED"
    assert report["registrations"][1]["state"] != "RECORDED_PASS"
    assert not report["backupRestorePairVerified"]
