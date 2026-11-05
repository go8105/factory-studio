"""Pinned history, pre-snapshot uncertainty, and conservative restriction plans."""

import pytest
from fs.core.backup import BackupError
from fs.core.security.journal import ZERO, append
from fs.gw import backup_journal as bridge
from test_security_journal import journal  # noqa: F401


def row(digest, kind, **fields):
    return {"digest": digest * 64, "payload": {"coverage": kind, **fields}}


def observed():
    records = [
        row("a", "core.security.intent.v1", userId=1),
        row("b", "core.security.intent.v1", userId=2),
        row("c", "core.security.intent.v1", userId=None),
        row("d", "gw.company.intent.v2", workspaceId=10, generationId=20),
        row("e", "hr.users.intent.v1", userId=3, workspaceId=10, generationId=20),
    ]
    return {"head": "e" * 64}, records


def test_pending_before_backup_and_unconfirmed_after_are_not_skipped(monkeypatch):
    full = observed()
    monkeypatch.setattr(
        bridge,
        "confirmed_digests",
        lambda c, rows: {r["digest"] for r in rows if r["digest"][0] in "abd"},
    )
    baseline = bridge.anchor(None, ({"head": "b" * 64}, full[1][:2]))
    assert baseline["confirmed"] == ["a" * 64, "b" * 64]
    # The second record was not visible in the backup DB snapshot.
    baseline["confirmed"].remove("b" * 64)
    plan = bridge.plan(None, baseline, full)
    assert plan["candidates"] == 4 and plan["unconfirmed"] == 2
    assert plan["users"] == [2, 3] and plan["scopes"] == [[10, 20]]
    assert plan["counterIntents"] == 1 and not plan["completenessConfirmed"]
    monkeypatch.setenv("FS_GW_JOURNAL_EXPECTED_HEAD", "e" * 64)
    bridge.validate_restore(baseline, plan)
    monkeypatch.setenv("FS_GW_JOURNAL_EXPECTED_HEAD", ZERO)
    with pytest.raises(BackupError):
        bridge.validate_restore(baseline, plan)


@pytest.mark.parametrize(
    "baseline",
    [
        {"head": "f" * 64, "records": 2, "confirmed": []},
        {"head": "b" * 64, "records": 99, "confirmed": []},
        {"head": "b" * 64, "records": 2, "confirmed": ["e" * 64]},
    ],
)
def test_rewound_missing_or_foreign_baseline_is_rejected(monkeypatch, baseline):
    monkeypatch.setattr(bridge, "confirmed_digests", lambda *a: set())
    with pytest.raises(BackupError):
        bridge.plan(None, baseline, observed())


def test_legacy_disabled_mode_is_explicit():
    assert bridge.anchor(None, None) is None
    assert bridge.plan(None, None, None) is None
    bridge.validate_restore(None, None)
    with pytest.raises(BackupError):
        bridge.plan(None, None, observed())
    with pytest.raises(BackupError):
        bridge.validate_restore({}, None)


def test_source_requires_pin_and_only_retains_metadata(journal, monkeypatch):  # noqa: F811
    directory, key = journal
    payload = {
        "coverage": "core.security.intent.v1",
        "userId": 1,
        "operation": "synthetic",
        "snapshot": {"private": "synthetic-metadata-only-test"},
    }
    head = append(directory, key, payload)
    monkeypatch.delenv("FS_GW_JOURNAL_EXPECTED_HEAD", raising=False)
    with pytest.raises(BackupError):
        bridge.source_records()
    monkeypatch.setenv("FS_GW_JOURNAL_EXPECTED_HEAD", ZERO)
    with pytest.raises(BackupError):
        bridge.source_records()
    monkeypatch.setenv("FS_GW_JOURNAL_EXPECTED_HEAD", head)
    state, records = bridge.source_records()
    assert state["head"] == head and "snapshot" not in records[0]["payload"]
