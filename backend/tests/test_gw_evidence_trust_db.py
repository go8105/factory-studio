"""Scoped signature ingestion, retained-source revocation and actual CLI on owned PG."""

# ruff: noqa: F401,F811
import base64
import json
import os
from copy import deepcopy

import pytest
from fs.common.errors import ApiError
from fs.gw.acceptance_sources import sign_current
from fs.gw.evidence_trust import from_environment
from fs.gw.operating_contract import canonical
from fs.gw.readiness import SOURCE_FIELD
from sqlalchemy import text
from test_gw_acceptance_sources_db import configured
from test_gw_company_work import api
from test_hr_work import company_env


def scope_for(co):
    return {
        "version": 1,
        "keys": {
            "source": {
                "workspaceIds": [str(co["companyId"])],
                "purposes": ["BACKUP", "RESTORE", "CHECKPOINT"],
            },
            "collector": {
                "workspaceIds": [str(co["companyId"])],
                "purposes": ["ACCEPTANCE_RECONCILIATION"],
            },
        },
    }


@pytest.mark.parametrize(
    "change",
    [
        "none",
        "source-as-issuer",
        "issuer-as-backup",
        "wrong-company",
        "revoked-restore",
        "aliased-key",
        "missing-scope",
    ],
)
def test_current_server_trust_is_rechecked_after_registration(
    company_env, monkeypatch, change
):
    args, _restore, source_signed = configured(company_env, monkeypatch)
    engine, co, admin, _ = company_env
    scopes = scope_for(co)
    monkeypatch.setenv("FS_GW_EVIDENCE_KEY_SCOPES", json.dumps(scopes))
    args["public_keys"] = from_environment()
    proof = sign_current(engine, **args)
    assert api(admin, co, "operating-evidence", proof).status_code == 200
    current = api(admin, co, "operations", method="GET").json()["data"]
    assert current["evidenceChecks"][2]["state"] == "PARTIAL" and not current["ready"]
    if change == "none":
        return
    if change == "source-as-issuer":
        payload = deepcopy(proof["envelope"])
        payload["signerKeyId"] = "source"
        assert (
            api(admin, co, "operating-evidence", source_signed(payload)).status_code
            == 400
        )
        return
    if change == "issuer-as-backup":
        with engine.connect() as c:
            payload = c.scalar(
                text(
                    "SELECT metrics FROM gw.operating_evidence WHERE workspace_id=:w AND kind='BACKUP'"
                ),
                {"w": co["companyId"]},
            )[SOURCE_FIELD]
        payload["signerKeyId"] = "collector"
        doc = {
            "envelope": payload,
            "signature": base64.b64encode(
                args["signer"].sign(canonical(payload))
            ).decode(),
        }
        assert api(admin, co, "operating-evidence", doc).status_code == 400
        return
    if change == "wrong-company":
        scopes["keys"]["source"]["workspaceIds"] = [str(co["companyId"] + 1000)]
    elif change == "revoked-restore":
        scopes["keys"]["source"]["purposes"] = ["BACKUP"]
    elif change == "aliased-key":
        raw = json.loads(os.environ["FS_GW_EVIDENCE_PUBLIC_KEYS"])
        raw["collector"] = raw["source"]
        monkeypatch.setenv("FS_GW_EVIDENCE_PUBLIC_KEYS", json.dumps(raw))
    elif change == "missing-scope":
        scopes["keys"].pop("source")
    monkeypatch.setenv("FS_GW_EVIDENCE_KEY_SCOPES", json.dumps(scopes))
    current = api(admin, co, "operations", method="GET").json()["data"]
    assert not current["ready"] and current["launchGate"]["unverifiedCount"] == 4
    if change in {"aliased-key", "missing-scope"}:
        assert all(c["state"] == "CONFIG_REQUIRED" for c in current["evidenceChecks"])
        with pytest.raises(ValueError):
            from_environment()
    else:
        assert current["evidenceChecks"][2]["state"] == "INVALID"
        args["public_keys"] = from_environment()
        with pytest.raises(ApiError):
            sign_current(engine, **args)


def test_actual_current_db_cli_uses_scoped_trust(company_env, monkeypatch, tmp_path):
    import test_gw_acceptance_sources_db as flow

    original = flow.configured

    def scoped(env, patch):
        args, restore, signed = original(env, patch)
        patch.setenv("FS_GW_EVIDENCE_KEY_SCOPES", json.dumps(scope_for(env[1])))
        args["public_keys"] = from_environment()
        return args, restore, signed

    monkeypatch.setattr(flow, "configured", scoped)
    flow.test_actual_cli_readonly_export_and_write_rejection(
        company_env, monkeypatch, tmp_path
    )


def test_company_mode_missing_scope_fails_server_verifier_configuration(
    company_env, monkeypatch
):
    from fs.gw.operating_evidence import verifier_config

    configured(company_env, monkeypatch)
    monkeypatch.setenv("FS_SECURITY_MODE", "COMPANY")
    monkeypatch.delenv("FS_GW_EVIDENCE_KEY_SCOPES", raising=False)
    with company_env[0].connect() as c, pytest.raises(ApiError) as failure:
        verifier_config(c)
    assert failure.value.status_code == 503
    assert failure.value.code == "SECURITY_CONFIGURATION_UNAVAILABLE"
