"""Bounded, signed source/checkpoint comparisons never grant final acceptance."""

import base64
from copy import deepcopy
from datetime import timedelta

import pytest
from test_gw_restore_recheck import prepared

from fs.gw.acceptance_reconciliation import sign_reconciliation
from fs.gw.operating_contract import canonical, verify_evidence
from fs.gw.restore_recheck import sign, verify
from fs.gw.source_checkpoint import changed_groups, state_digest


def observation(obs, ctx, mode="match"):
    saved = {
        "core": {"users": [{"id": 1, "state": "active"}]},
        "gw": {"roles": []},
        "hr": [],
    }
    current = deepcopy(saved)
    if mode == "changed":
        current["core"]["users"][0]["state"] = "disabled"
    measured = mode != "unavailable"
    matches = mode == "match"
    return {
        "version": 1,
        "scope": "CURRENT_SOURCE_CHECKPOINT_FIELDS",
        "observedAt": ctx["now"].isoformat(),
        "sourceIdentity": obs["sourceIdentity"],
        "checkpointStateDigest": state_digest(saved),
        "currentStateDigest": state_digest(current) if measured else None,
        "sourceMeasured": measured,
        "contextMatches": mode != "context" if measured else None,
        "changedGroups": changed_groups(saved, current) if measured else None,
        "reason": "MATCH"
        if matches
        else "CHANGED"
        if measured
        else "MEASUREMENT_UNAVAILABLE",
        "result": "PARTIAL" if matches else "BLOCKED",
    }


def proof(mode="match"):
    docs, obs, collector, key, ctx = prepared()
    document = sign(
        docs["RESTORE"],
        measurement=obs,
        source_observation=observation(obs, ctx, mode),
        checked_at=ctx["now"].isoformat(),
        signer=key,
        signer_id="rechecker",
        **ctx,
    )
    return document, docs, collector, key, ctx


@pytest.mark.parametrize("mode", ["match", "changed", "context", "unavailable"])
def test_signed_current_source_is_bound_and_never_promotes(mode):
    document, docs, collector, _key, ctx = proof(mode)
    checked = verify(document, docs["RESTORE"], **ctx)
    assert checked.version == 2
    assert (
        checked.measurement.result == "PARTIAL"
    )  # Closed target alone cannot pass a changed source.
    assert checked.result == ("PARTIAL" if mode == "match" else "BLOCKED")
    result = sign_reconciliation(
        docs,
        signer=collector,
        signer_id="collector",
        database_observed_at=ctx["now"].isoformat(),
        restore_recheck=document,
        **ctx,
    )
    data = verify_evidence(result["envelope"], result["signature"], **ctx)
    assert data.metrics.acceptance_diagnostics.version == 4
    assert data.result == ("PARTIAL" if mode == "match" else "FAIL")
    assert data.metrics.acceptance_diagnostics.final_release == "UNVERIFIED"


@pytest.mark.parametrize(
    "change",
    [
        "physical",
        "old",
        "future",
        "age",
        "float",
        "unknown",
        "invented",
        "counts",
        "result",
        "tamper",
    ],
)
def test_invalid_source_observation_cannot_replace_known_checkpoint(change):
    document, docs, _collector, key, ctx = proof()
    source = document["envelope"]["sourceObservation"]
    if change == "physical":
        source["sourceIdentity"] = "f" * 64
    elif change in {"old", "future"}:
        source["observedAt"] = (
            ctx["now"] + timedelta(seconds=31 if change == "future" else -31)
        ).isoformat()
    elif change == "age":
        source["observedAt"] = (ctx["now"] - timedelta(seconds=11)).isoformat()
        ctx["now"] += timedelta(minutes=14, seconds=50)
    elif change == "float":
        source["version"] = 1.0
    elif change == "unknown":
        source["complete"] = True
    elif change == "invented":
        source["sourceMeasured"] = False
    elif change == "counts":
        source["changedGroups"]["core"] = 1
    elif change == "result":
        document["envelope"]["result"] = "BLOCKED"
    else:
        document["envelope"]["signerKeyId"] = "collector"
    document["signature"] = base64.b64encode(
        key.sign(canonical(document["envelope"]))
    ).decode()
    with pytest.raises((ValueError, TypeError)):
        verify(document, docs["RESTORE"], **ctx)


def test_digest_ignores_query_row_order_but_detects_removed_or_changed_rows():
    saved = {
        "core": {"roles": [{"user": 1}, {"user": 2}]},
        "gw": {"guards": {"a": "x"}},
        "hr": [],
    }
    current = deepcopy(saved)
    current["core"]["roles"].reverse()
    assert state_digest(saved) == state_digest(current)
    assert changed_groups(saved, current) == {"core": 0, "gw": 0, "hr": 0}
    current["core"]["roles"].pop()
    current["gw"]["guards"]["a"] = "y"
    current["hr"].append({"active": False})
    assert changed_groups(saved, current) == {"core": 1, "gw": 1, "hr": 1}
    current["core"]["added"] = []
    assert changed_groups(saved, current)["core"] == 2


@pytest.mark.parametrize("source_changed", [False, True])
@pytest.mark.parametrize("journal_blocked", [False, True])
def test_source_and_journal_observations_keep_either_failure(
    source_changed, journal_blocked
):
    import json

    from test_gw_journal_acceptance import prepared as journal_prepared

    from fs.gw.evidence_trust import load

    document, docs, collector, _key, ctx = proof(
        "changed" if source_changed else "match"
    )
    _, _, observer, journal, _ = journal_prepared()
    public = {
        name: base64.b64encode(raw).decode() for name, raw in ctx["public_keys"].items()
    }
    public["observer"] = base64.b64encode(
        observer.public_key().public_bytes_raw()
    ).decode()
    uses = {
        "runner-1": ["BACKUP", "RESTORE"],
        "collector": ["ACCEPTANCE_RECONCILIATION"],
        "rechecker": ["RESTORE_RECHECK"],
        "observer": ["JOURNAL_OBSERVATION"],
    }
    scopes = {
        "version": 1,
        "keys": {
            name: {"workspaceIds": [str(ctx["workspace_id"])], "purposes": purposes}
            for name, purposes in uses.items()
        },
    }
    ctx["public_keys"] = load(json.dumps(public), json.dumps(scopes), mode="COMPANY")
    if journal_blocked:
        journal["dispositions"]["AUDIT_CONFIRMED"] -= 1
        journal["dispositions"]["PENDING"] += 1
        journal["result"] = "BLOCKED"
    journal_document = {
        "envelope": journal,
        "signature": base64.b64encode(observer.sign(canonical(journal))).decode(),
    }
    result = sign_reconciliation(
        docs,
        signer=collector,
        signer_id="collector",
        database_observed_at=ctx["now"].isoformat(),
        restore_recheck=document,
        journal_observation=journal_document,
        **ctx,
    )
    data = verify_evidence(result["envelope"], result["signature"], **ctx)
    assert data.result == ("FAIL" if source_changed or journal_blocked else "PARTIAL")
    assert data.metrics.acceptance_diagnostics.restore_recheck.envelope["version"] == 2
    assert data.metrics.acceptance_diagnostics.journal_observation.envelope == journal
