"""Operator diagnostics stay allowlisted and fail closed without exposing settings."""

# ruff: noqa: F401,F811
import pytest
from fs.gw import catalog_trust_store as floor
from fs.gw.evidence_trust import from_environment
from fs.gw.trust_configuration import ISSUES, TrustConfigurationError, guidance
from test_gw_catalog_trust_store import environment, expanded, initialize, setup


@pytest.mark.parametrize("code", list(ISSUES))
def test_guidance_is_fixed_and_generic_exception_is_compatible(code):
    error = TrustConfigurationError(code)
    assert isinstance(error, ValueError)
    assert str(error) == "catalog lifecycle trust unavailable"
    assert guidance(code)["owner"] == "SERVER_OPERATOR"
    assert guidance(code)["code"] == code


@pytest.mark.parametrize("value", [None, [], {}, "private/key/path", "__proto__"])
def test_unknown_guidance_never_echoes_input(value):
    assert guidance(value) == guidance("VERIFIER_CONFIGURATION")


@pytest.mark.parametrize(
    "change,code",
    [
        ("keys", "VERIFIER_CONFIGURATION"),
        ("lifecycle", "CATALOG_LIFECYCLE"),
        ("missing", "TRUST_STORE_REQUIRED"),
        ("unreadable", "TRUST_STORE_UNAVAILABLE"),
        ("settings", "TRUST_SETTINGS_MISMATCH"),
        ("pending", "TRUST_UPDATE_PENDING"),
        ("receiving", "TRUST_RECOVERY_PENDING"),
    ],
)
def test_environment_classifies_only_verified_failure_stage(
    setup, monkeypatch, change, code
):
    path, _, keys = initialize(setup, monkeypatch)
    if change == "keys":
        monkeypatch.setenv("FS_GW_EVIDENCE_PUBLIC_KEYS", "private/key/path")
    elif change == "lifecycle":
        monkeypatch.setenv("FS_GW_CATALOG_KEY_LIFECYCLE", "private/key/path")
    elif change == "missing":
        monkeypatch.delenv(floor.ENV)
    elif change == "unreadable":
        monkeypatch.setenv(floor.ENV, str(path / "missing"))
    elif change == "settings":
        environment(monkeypatch, expanded(keys))
    elif change == "pending":
        (path / ".trust-head.pending").write_bytes(b"private/key/path")
    else:
        (path / ".trust-receiving").write_bytes(b"private/key/path")
    with pytest.raises(TrustConfigurationError) as caught:
        from_environment()
    assert caught.value.code == code
    assert "private" not in str(caught.value)
