"""Interruption proofs bind receiver floors and retain every unknown original byte."""

# ruff: noqa: F401,F811
import base64
import json
import os
from copy import deepcopy
from datetime import timedelta

import pytest
from cryptography.exceptions import InvalidSignature
from test_gw_catalog_store import invoke, setup
from test_gw_catalog_transfer import outgoing, receive, receiver

from fs.gw import catalog_recovery as recovery
from fs.gw import catalog_store as store
from fs.gw import catalog_transfer as transfer
from fs.gw.checkpoint_catalog import DOMAIN, CatalogConfig, verify_document
from fs.gw.operating_contract import canonical


def interrupt(parts, patch, *, size=None, initial=False, complete=False):
    first = None if initial else invoke(parts)
    original = store.write_new
    with patch.context() as child:

        def cut(root, name, raw):
            if name.startswith("catalog-"):
                if complete:
                    original(root, name, raw)
                elif size is not None:
                    original(root, name, raw[:size])
                raise OSError("interrupted before activation")
            return original(root, name, raw)

        child.setattr(store, "write_new", cut)
        with pytest.raises(OSError):
            invoke(parts, first)
    return first


def recover(parts):
    folder = parts[0]
    pin = (
        store.digest((folder / store.PIN).read_bytes())
        if (folder / store.PIN).exists()
        else "ABSENT"
    )
    return invoke(
        parts, operation="recover-pending", expected_pin_digest=pin, initialize=False
    )


def target(parts, report):
    data = (
        parts[0] / store.filename(report["revision"], report["catalogDigest"])
    ).read_bytes()
    config = CatalogConfig(
        version=1,
        provider="SIGNED_SNAPSHOT_FILE",
        catalogId=report["catalogId"],
        file="/unused",
        digest=report["catalogDigest"],
    )
    return verify_document(
        data,
        config,
        public_keys=parts[1]["public_keys"],
        workspace_id=parts[1]["context"].workspace_id,
    ), data


@pytest.mark.parametrize("initial", [False, True])
@pytest.mark.parametrize("kind", ["missing", "empty", "truncated", "complete"])
def test_recovery_proof_and_unknown_bytes_cross_receiver_without_becoming_pass(
    setup, monkeypatch, initial, kind
):
    first = interrupt(
        setup,
        monkeypatch,
        size={"empty": 0, "truncated": 8}.get(kind),
        initial=initial,
        complete=kind == "complete",
    )
    before = {p.name: p.read_bytes() for p in setup[0].glob("catalog-*.json")}
    result = recover(setup)
    catalog, _ = target(setup, result)
    assert (
        catalog.version == 2
        and catalog.records[0].result == "PARTIAL"
        and catalog.records[0].head is None
    )
    proof = recovery.verify(
        catalog,
        public_keys=setup[1]["public_keys"],
        workspace_id=setup[2]["workspace_id"],
    )
    assert proof.base_digest == (first["catalogDigest"] if first else "ABSENT")
    assert proof.disposition == "PARTIAL_HEAD_UNKNOWN" and len(proof.slots) == 1
    slot = proof.slots[0]
    assert (slot.actual_digest is None) == (kind == "missing")
    raw, anchor = outgoing(setup)
    packet = json.loads(raw)
    assert packet["version"] == 2 and len(packet["artifacts"]) == (kind != "missing")
    dest = receiver(setup)
    installed = receive(setup, dest, raw, anchor)
    assert installed["result"] == "PARTIAL" and installed["ready"] is False
    assert installed["catalogDigest"] == result["catalogDigest"]
    assert all((dest / name).read_bytes() == data for name, data in before.items())
    assert all((setup[0] / name).read_bytes() == data for name, data in before.items())
    refreshed = invoke(setup, result, operation="refresh")
    recheck_catalog, _ = target(setup, refreshed)
    assert recheck_catalog.recovery_proof == catalog.recovery_proof
    assert recheck_catalog.records == catalog.records


def test_receiver_base_is_exact_and_cannot_start_inside_a_signed_unknown_interval(
    setup, monkeypatch
):
    first = invoke(setup)
    initial_raw, initial_anchor = outgoing(setup)
    dest = receiver(setup)
    installed = receive(setup, dest, initial_raw, initial_anchor)
    original = store.write_new
    with monkeypatch.context() as patch:

        def stop(root, name, data):
            if name.startswith("catalog-"):
                raise OSError("interrupted")
            return original(root, name, data)

        patch.setattr(store, "write_new", stop)
        with pytest.raises(OSError):
            invoke(setup, first)
    repaired = recover(setup)
    raw, anchor = outgoing(setup, first["revision"], first["catalogDigest"])
    current = receive(setup, dest, raw, anchor, installed)
    assert (
        current["result"] == "PARTIAL" and current["revision"] == repaired["revision"]
    )
    with pytest.raises(ValueError):
        outgoing(setup, 2, "0" * 64)


def test_new_pass_after_recovery_requires_new_signed_capture_and_keeps_proof_history(
    setup, monkeypatch
):
    interrupt(setup, monkeypatch, size=8)
    repaired = recover(setup)
    old = invoke(setup, repaired)
    assert old["result"] == "FAIL"
    now = setup[1]["now"]
    setup[4](now + timedelta(seconds=1))
    fresh = invoke(setup, old, now=now + timedelta(seconds=2))
    raw, anchor = outgoing(setup, now=now + timedelta(seconds=2))
    dest = receiver(setup)
    result = receive(setup, dest, raw, anchor, now=now + timedelta(seconds=2))
    assert (
        result["result"] == "PASS" and result["catalogDigest"] == fresh["catalogDigest"]
    )
    assert any(
        json.loads(p.read_bytes()).get("envelope", {}).get("version") == 2
        for p in dest.glob("catalog-*.json")
        if p.stat().st_size > 8
    )


@pytest.mark.parametrize(
    "problem",
    [
        "proof_signature",
        "outer_signature",
        "base_digest",
        "base_sequence",
        "target",
        "scope",
        "record",
        "slots",
        "intent",
        "pass",
        "head",
        "proof_key",
    ],
)
def test_invalid_recovery_proof_is_rejected_even_if_outer_issuer_resigns(
    setup, monkeypatch, problem
):
    interrupt(setup, monkeypatch)
    result = recover(setup)
    _, original = target(setup, result)
    document = json.loads(original)
    envelope = document["envelope"]
    proof = envelope["recoveryProof"]
    data = proof["envelope"]
    if problem == "proof_signature":
        proof["signature"] = base64.b64encode(b"z" * 64).decode()
    elif problem == "outer_signature":
        document["signature"] = base64.b64encode(b"z" * 64).decode()
    elif problem == "base_digest":
        data["baseDigest"] = "ABSENT"
    elif problem == "base_sequence":
        data["baseSequence"] = 999
    elif problem == "target":
        data["targetRevision"] += 1
    elif problem == "scope":
        data["workspaceId"] = "999"
    elif problem == "record":
        envelope["records"][0]["codeRevision"] = "a" * 40
    elif problem == "slots":
        data["slots"] = []
    elif problem == "intent":
        data["intent"]["catalogId"] = "00000000-0000-4000-8000-000000000000"
    elif problem == "pass":
        envelope["records"][0]["result"] = "PASS"
    elif problem == "head":
        envelope["records"][0]["head"] = setup[3]
    else:
        data["signerKeyId"] = "checkpoint"
    if problem not in {"proof_signature", "outer_signature", "proof_key"}:
        proof["signature"] = base64.b64encode(
            setup[1]["signer"].sign(recovery.DOMAIN + canonical(data))
        ).decode()
    if problem != "outer_signature":
        document["signature"] = base64.b64encode(
            setup[1]["signer"].sign(DOMAIN + canonical(envelope))
        ).decode()
    raw = canonical(document)
    config = CatalogConfig(
        version=1,
        provider="SIGNED_SNAPSHOT_FILE",
        catalogId=result["catalogId"],
        file="/unused",
        digest=store.digest(raw),
    )
    with pytest.raises((ValueError, KeyError, InvalidSignature)):
        verify_document(
            raw,
            config,
            public_keys=setup[1]["public_keys"],
            workspace_id=setup[2]["workspace_id"],
        )


@pytest.mark.parametrize(
    "problem",
    [
        "missing_artifact",
        "extra_artifact",
        "wrong_bytes",
        "wrong_expected_digest",
        "artifact_as_snapshot",
        "downgrade",
        "wrong_base_bytes",
    ],
)
def test_transfer_cannot_drop_or_reclassify_unknown_originals(
    setup, monkeypatch, problem
):
    interrupt(setup, monkeypatch, size=8)
    recover(setup)
    raw, anchor = outgoing(setup)
    packet = json.loads(raw)
    if problem == "missing_artifact":
        packet["artifacts"] = []
    elif problem == "extra_artifact":
        packet["artifacts"].append(deepcopy(packet["artifacts"][0]))
    elif problem == "wrong_bytes":
        packet["artifacts"][0]["content"] = base64.b64encode(b"tampered").decode()
    elif problem == "wrong_expected_digest":
        packet["artifacts"][0]["digest"] = "0" * 64
    elif problem == "artifact_as_snapshot":
        item = packet["artifacts"][0]
        packet["snapshots"].insert(
            1, {k: item[k] for k in ("version", "revision", "digest", "content")}
        )
    elif problem == "downgrade":
        packet["version"] = 1
        packet.pop("artifacts")
    else:
        packet["baseRevision"] = 1
        packet["baseDigest"] = "0" * 64
    data = canonical(packet)
    dest = receiver(setup)
    anchor["transferDigest"] = store.digest(data)
    with pytest.raises((ValueError, KeyError, InvalidSignature)):
        receive(setup, dest, data, anchor)
    assert (dest / store.PENDING).exists() and not (dest / store.PIN).exists()


def test_gap_original_changed_or_missing_after_signed_recovery_blocks_export(
    setup, monkeypatch
):
    interrupt(setup, monkeypatch, size=8)
    recover(setup)
    gap = next(p for p in setup[0].glob("catalog-*.json") if p.stat().st_size == 8)
    gap.write_bytes(b"different")
    with pytest.raises(ValueError):
        outgoing(setup)
    gap.unlink()  # Test damage, never a production recovery instruction.
    with pytest.raises(KeyError):
        outgoing(setup)


@pytest.mark.parametrize("after_pin", [False, True])
def test_recovery_interrupted_again_extends_exact_actual_base(
    setup, monkeypatch, after_pin
):
    interrupt(setup, monkeypatch)
    original_activate = store.activate
    with monkeypatch.context() as patch:

        def cut(root, path, catalog, data, expected):
            if after_pin:
                raw_pin = (
                    canonical(
                        {
                            "version": 1,
                            "provider": "SIGNED_SNAPSHOT_FILE",
                            "catalogId": catalog.catalog_id,
                            "file": str(
                                path
                                / store.filename(catalog.revision, store.digest(data))
                            ),
                            "digest": store.digest(data),
                        }
                    )
                    + b"\n"
                )
                temp = ".pin-" + "a" * 32
                store.write_new(root, temp, raw_pin)
                os.replace(temp, store.PIN, src_dir_fd=root, dst_dir_fd=root)
                os.fsync(root)
            raise OSError("recovery interrupted")

        patch.setattr(store, "activate", cut)
        with pytest.raises(OSError):
            recover(setup)
    assert store.activate is original_activate
    final = recover(setup)
    catalog, _ = target(setup, final)
    proof = recovery.Proof.model_validate(catalog.recovery_proof).envelope
    assert proof.base_revision == (3 if after_pin else 1)
    raw, anchor = outgoing(setup)
    installed = receive(setup, receiver(setup), raw, anchor)
    assert (
        installed["catalogDigest"] == final["catalogDigest"]
        and installed["result"] == "PARTIAL"
    )


def test_interrupted_receiving_recovery_artifacts_retries_same_zero_byte_original(
    setup, monkeypatch
):
    interrupt(setup, monkeypatch, size=0)
    recover(setup)
    raw, anchor = outgoing(setup)
    dest = receiver(setup)
    original_link = os.link
    with monkeypatch.context() as patch:

        def cut(src, name, **kw):
            result = original_link(src, name, **kw)
            if name.startswith("catalog-"):
                raise OSError("artifact publish interrupted after link")
            return result

        patch.setattr(os, "link", cut)
        with pytest.raises(OSError):
            receive(setup, dest, raw, anchor)
    assert (dest / store.PENDING).exists()
    installed = receive(setup, dest, raw, anchor, initialize=False, resume=True)
    assert installed["result"] == "PARTIAL"
    assert any(
        p.stat().st_size == 0 and p.stat().st_nlink == 1
        for p in dest.glob("catalog-*.json")
    )


def test_present_valid_failure_stays_an_unknown_original_never_becomes_success(
    setup, monkeypatch
):
    first = invoke(setup)
    original = store.write_new
    with monkeypatch.context() as patch:

        def cut(root, name, data):
            result = original(root, name, data)
            if name.startswith("catalog-"):
                assert json.loads(data)["envelope"]["records"][0]["result"] == "FAIL"
                raise OSError("FAIL publication interrupted")
            return result

        patch.setattr(store, "write_new", cut)
        with pytest.raises(OSError):
            invoke(setup, first, head_path=setup[0] / "missing")
    repaired = recover(setup)
    raw, anchor = outgoing(setup)
    packet = json.loads(raw)
    assert (
        json.loads(base64.b64decode(packet["artifacts"][0]["content"]))["envelope"][
            "records"
        ][0]["result"]
        == "FAIL"
    )
    installed = receive(setup, receiver(setup), raw, anchor)
    assert (
        installed["result"] == "PARTIAL"
        and installed["catalogDigest"] == repaired["catalogDigest"]
    )
    assert invoke(setup, repaired)["result"] == "FAIL"


@pytest.mark.parametrize(
    "damage", ["key_revoked", "scope", "late_origin", "bool_version", "extra"]
)
def test_recovery_requires_current_authority_and_exact_origin_format(
    setup, monkeypatch, damage
):
    interrupt(setup, monkeypatch)
    report = recover(setup)
    _, original = target(setup, report)
    document = json.loads(original)
    envelope = document["envelope"]
    proof = envelope["recoveryProof"]
    keys = setup[1]["public_keys"]
    if damage == "key_revoked":
        from fs.gw.evidence_trust import EvidenceTrust

        keys = EvidenceTrust(dict(keys), {})
    elif damage == "scope":
        proof["envelope"]["generationId"] = "999"
    elif damage == "late_origin":
        envelope["publishedAt"] = (setup[1]["now"] + timedelta(seconds=1)).isoformat()
    elif damage == "bool_version":
        proof["envelope"]["version"] = True
    else:
        proof["envelope"]["operatorApproved"] = True
    proof["signature"] = base64.b64encode(
        setup[1]["signer"].sign(recovery.DOMAIN + canonical(proof["envelope"]))
    ).decode()
    document["signature"] = base64.b64encode(
        setup[1]["signer"].sign(DOMAIN + canonical(envelope))
    ).decode()
    raw = canonical(document)
    config = CatalogConfig(
        version=1,
        provider="SIGNED_SNAPSHOT_FILE",
        catalogId=report["catalogId"],
        file="/unused",
        digest=store.digest(raw),
    )
    with pytest.raises((ValueError, KeyError, InvalidSignature)):
        verify_document(
            raw, config, public_keys=keys, workspace_id=setup[2]["workspace_id"]
        )


def test_resigned_proof_with_wrong_predecessor_digest_cannot_extend_receiver(
    setup, monkeypatch
):
    interrupt(setup, monkeypatch)
    recover(setup)
    raw, anchor = outgoing(setup)
    packet = json.loads(raw)
    snapshot = packet["snapshots"][-1]
    document = json.loads(base64.b64decode(snapshot["content"]))
    proof = document["envelope"]["recoveryProof"]
    proof["envelope"]["baseDigest"] = "0" * 64
    proof["signature"] = base64.b64encode(
        setup[1]["signer"].sign(recovery.DOMAIN + canonical(proof["envelope"]))
    ).decode()
    document["signature"] = base64.b64encode(
        setup[1]["signer"].sign(DOMAIN + canonical(document["envelope"]))
    ).decode()
    data = canonical(document)
    snapshot.update(content=base64.b64encode(data).decode(), digest=store.digest(data))
    encoded = canonical(packet)
    anchor["transferDigest"] = store.digest(encoded)
    with pytest.raises(ValueError, match="receiver predecessor"):
        receive(setup, receiver(setup), encoded, anchor)


def test_signed_absence_does_not_accept_a_file_appearing_after_recovery(
    setup, monkeypatch
):
    interrupt(setup, monkeypatch)
    repaired = recover(setup)
    unexpected = setup[0] / store.filename(repaired["revision"] - 1, "0" * 64)
    unexpected.write_bytes(b"unexpected")
    unexpected.chmod(0o600)
    with pytest.raises(ValueError, match="absent interruption file appeared"):
        outgoing(setup)


def test_recovery_gap_limit_does_not_drop_pending_or_create_an_unbounded_proof(
    setup, monkeypatch
):
    interrupt(setup, monkeypatch)
    with monkeypatch.context() as patch:
        patch.setattr(recovery, "MAX_SLOTS", 0)
        with pytest.raises(ValueError):
            recover(setup)
    assert (setup[0] / store.PENDING).exists()
    assert len(list(setup[0].glob("catalog-*.json"))) == 1


def test_changed_pending_pin_anchor_cannot_become_signed_recovery(setup, monkeypatch):
    interrupt(setup, monkeypatch)
    pending = setup[0] / store.PENDING
    intent = json.loads(pending.read_bytes())
    intent["expectedPinDigest"] = "0" * 64
    pending.write_bytes(canonical(intent))
    with pytest.raises(ValueError, match="reservation does not match current pin"):
        recover(setup)
    assert len(list(setup[0].glob("catalog-*.json"))) == 1


def test_recovery_after_interrupted_refresh_with_unchanged_event_number(
    setup, monkeypatch
):
    first = invoke(setup)
    original_unlink = os.unlink
    with monkeypatch.context() as patch:

        def cut(name, **kw):
            if name == store.PENDING:
                raise OSError("refresh pointer applied, completion unknown")
            return original_unlink(name, **kw)

        patch.setattr(os, "unlink", cut)
        with pytest.raises(OSError):
            invoke(setup, first, operation="refresh")
    result = recover(setup)
    raw, anchor = outgoing(setup)
    installed = receive(setup, receiver(setup), raw, anchor)
    assert result["sequence"] == 3 and installed["result"] == "PARTIAL"
