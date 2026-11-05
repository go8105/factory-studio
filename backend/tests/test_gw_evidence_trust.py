"""Purpose/company grants come from deployment settings, never signed caller flags."""

import base64
import importlib.util
import json
from copy import deepcopy
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fs.common.errors import ApiError
from fs.core.backup import BackupError
from fs.gw.acceptance_reconciliation import sign_reconciliation
from fs.gw.evidence_trust import authorize, load
from fs.gw.operating_contract import canonical, verify_evidence
from test_gw_acceptance_collection import fixture, signed


def settings():
    a, b = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    keys = {
        "source": base64.b64encode(a.public_key().public_bytes_raw()).decode(),
        "collector": base64.b64encode(b.public_key().public_bytes_raw()).decode(),
    }
    scopes = {
        "version": 1,
        "keys": {
            "source": {
                "workspaceIds": ["10"],
                "purposes": ["BACKUP", "RESTORE", "CHECKPOINT"],
            },
            "collector": {
                "workspaceIds": ["10"],
                "purposes": ["ACCEPTANCE_RECONCILIATION"],
            },
        },
    }
    return a, b, keys, scopes


@pytest.mark.parametrize(
    "change",
    [
        "none",
        "missing",
        "empty",
        "wrong-version",
        "bool-version",
        "extra",
        "unknown-key",
        "missing-key",
        "alias",
        "mixed-issuer",
        "wildcard",
        "integer-company",
        "bool-company",
        "zero-company",
        "huge-company",
        "duplicate-company",
        "duplicate-purpose",
        "unknown-purpose",
        "empty-purpose",
        "bad-record",
        "bad-public",
        "bad-key-id",
        "bad-key-size",
        "unknown-mode",
        "duplicate-json",
    ],
)
def test_strict_company_trust_configuration(change):
    _, _, keys, scopes = settings()
    mode = "COMPANY"
    record = scopes["keys"]["source"]
    if change == "missing":
        scopes = None
    elif change == "empty":
        scopes = {}
    elif change == "wrong-version":
        scopes["version"] = 2
    elif change == "bool-version":
        scopes["version"] = True
    elif change == "extra":
        scopes["ready"] = True
    elif change == "unknown-key":
        scopes["keys"]["other"] = deepcopy(record)
    elif change == "missing-key":
        scopes["keys"].pop("collector")
    elif change == "alias":
        keys["collector"] = keys["source"]
    elif change == "mixed-issuer":
        record["purposes"].append("ACCEPTANCE_RECONCILIATION")
    elif change == "wildcard":
        record["workspaceIds"] = ["*"]
    elif change == "integer-company":
        record["workspaceIds"] = [10]
    elif change == "bool-company":
        record["workspaceIds"] = [True]
    elif change == "zero-company":
        record["workspaceIds"] = ["0"]
    elif change == "huge-company":
        record["workspaceIds"] = ["9999999999999999999"]
    elif change == "duplicate-company":
        record["workspaceIds"] = ["10", "10"]
    elif change == "duplicate-purpose":
        record["purposes"].append("BACKUP")
    elif change == "unknown-purpose":
        record["purposes"] = ["FINAL_RELEASE_PASS"]
    elif change == "empty-purpose":
        record["purposes"] = []
    elif change == "bad-record":
        record["url"] = "must not copy arbitrary data"
    elif change == "bad-public":
        keys["source"] = "invalid"
    elif change == "bad-key-id":
        keys["bad id"] = keys.pop("source")
    elif change == "bad-key-size":
        keys["source"] = base64.b64encode(b"short").decode()
    elif change == "unknown-mode":
        mode = "invalid"
    raw = json.dumps(scopes) if scopes is not None else None
    if change == "duplicate-json":
        raw = '{"version":1,"version":1,"keys":{}}'
    if change == "none":
        trust = load(json.dumps(keys), raw, mode=mode)
        assert trust.scoped
        authorize(trust, "source", "BACKUP", "10")
        authorize(trust, "collector", "ACCEPTANCE", "10")
        for key, kind, company in [
            ("source", "ACCEPTANCE", "10"),
            ("collector", "BACKUP", "10"),
            ("source", "BACKUP", "11"),
            ("source", "CHECKPOINT_HEAD", "11"),
        ]:
            with pytest.raises(ValueError):
                authorize(trust, key, kind, company)
    else:
        with pytest.raises(ValueError):
            load(json.dumps(keys), raw, mode=mode)


@pytest.mark.parametrize("mode", ["PUBLIC_DEMO", "TEAM_TEST"])
def test_unscoped_compatibility_is_explicitly_non_company(mode):
    _, _, keys, _ = settings()
    trust = load(json.dumps(keys), mode=mode)
    assert not trust.scoped


def test_correct_signature_still_requires_purpose_and_company_and_separate_issuer():
    source, issuer, keys, scopes = settings()
    _, payloads, ctx = fixture()
    for value in payloads.values():
        value["signerKeyId"] = "source"
    ctx["public_keys"] = load(json.dumps(keys), json.dumps(scopes), mode="COMPANY")
    docs = signed(payloads, source)
    result = sign_reconciliation(docs, signer=issuer, signer_id="collector", **ctx)
    assert (
        verify_evidence(result["envelope"], result["signature"], **ctx).result
        == "PARTIAL"
    )
    with pytest.raises(ApiError):
        sign_reconciliation(docs, signer=source, signer_id="source", **ctx)
    payload = deepcopy(payloads["BACKUP"])
    payload["signerKeyId"] = "collector"
    with pytest.raises(ApiError):
        verify_evidence(
            payload, base64.b64encode(issuer.sign(canonical(payload))).decode(), **ctx
        )
    promoted = deepcopy(result["envelope"])
    promoted["result"] = "PASS"
    with pytest.raises(ApiError):
        verify_evidence(
            promoted, base64.b64encode(issuer.sign(canonical(promoted))).decode(), **ctx
        )
    scopes["keys"]["source"]["workspaceIds"] = ["11"]
    ctx["public_keys"] = load(json.dumps(keys), json.dumps(scopes))
    with pytest.raises(ApiError):
        sign_reconciliation(docs, signer=issuer, signer_id="collector", **ctx)


def test_internal_backup_and_checkpoint_bundles_require_scoped_source_signers():
    source, issuer, keys, scopes = settings()
    trust = load(json.dumps(keys), json.dumps(scopes))
    path = Path(__file__).parents[2] / "tools/gw_backup.py"
    spec = importlib.util.spec_from_file_location("trust_backup", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for kind in ["BACKUP", "CHECKPOINT", "CHECKPOINT_HEAD"]:
        payload = {"kind": kind, "scope": {"workspaceId": "10"}}
        config = {"public": trust, "signer": source, "signerId": "source"}
        doc = module.signed_document(payload, config)
        assert module.verified_document(doc, config) == payload
        config.update(signer=issuer, signerId="collector")
        with pytest.raises(ValueError):
            module.signed_document(payload, config)
        forged = {
            "payload": payload,
            "signerKeyId": "collector",
            "signature": base64.b64encode(
                issuer.sign(module.CONTEXT + canonical(payload))
            ).decode(),
        }
        with pytest.raises(BackupError):
            module.verified_document(forged, config)
        payload["scope"]["workspaceId"] = "11"
        forged = {
            "payload": payload,
            "signerKeyId": "source",
            "signature": base64.b64encode(
                source.sign(module.CONTEXT + canonical(payload))
            ).decode(),
        }
        with pytest.raises(BackupError):
            module.verified_document(forged, config)
