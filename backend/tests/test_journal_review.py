"""A diagnostic review never turns missing evidence into release permission."""

import json
import stat

import pytest
from fs.core.backup import BackupError
from fs.core.security.journal_review import GUIDANCE, build, write


def test_review_keeps_unknowns_and_excludes_payload_secrets(tmp_path):
    records = [
        {"digest": str(i) * 64, "payload": {"snapshot": "synthetic-secret"}}
        for i in range(6)
    ]
    dispositions = dict(zip((r["digest"] for r in records), GUIDANCE, strict=True))
    report = build({"head": "5" * 64}, records, dispositions)
    assert report["records"] == 6
    assert report["settledRecords"] == 2
    assert not report["allTransactionsSettled"]
    assert not report["releaseAuthorized"] and not report["checkpointInput"]
    assert not report["completenessConfirmed"]
    assert len(report["operatorChecks"]) == 5
    assert "synthetic-secret" not in json.dumps(report)
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    path = directory / "review.json"
    write(path, report)
    assert json.loads(path.read_text()) == report
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    with pytest.raises(FileExistsError):
        write(path, report)
    assert json.loads(path.read_text()) == report
    link = directory / "link"
    link.symlink_to(path)
    with pytest.raises(FileExistsError):
        write(link, report)


def test_empty_and_all_settled_reviews_are_not_release_approvals():
    empty = build({"head": "0" * 64}, [], {})
    assert not empty["allTransactionsSettled"] and not empty["releaseAuthorized"]
    settled = build(
        {"head": "a" * 64}, [{"digest": "a" * 64}], {"a" * 64: "ABORT_CONFIRMED"}
    )
    assert settled["allTransactionsSettled"]
    assert not settled["releaseAuthorized"] and not settled["completenessConfirmed"]


@pytest.mark.parametrize("dispositions", [{}, {"a": "ACCEPTED"}, {"b": "UNKNOWN"}])
def test_review_rejects_missing_extra_or_manual_override_states(dispositions):
    with pytest.raises(BackupError):
        build({"head": "a"}, [{"digest": "a"}], dispositions)


def test_review_rejects_public_directory(tmp_path):
    tmp_path.chmod(0o755)
    with pytest.raises(BackupError):
        write(tmp_path / "review.json", {})
