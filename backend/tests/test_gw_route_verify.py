import importlib.util
from pathlib import Path

import pytest


def runner():
    path = Path(__file__).resolve().parents[2] / "tools/gw_route_verify.py"
    spec = importlib.util.spec_from_file_location("route_verify", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "change",
    [
        "none",
        "failure",
        "error",
        "skip",
        "missing",
        "duplicate",
        "wrong-class",
        "extra",
    ],
)
def test_junit_probe_selection_never_promotes_failures_or_skips(tmp_path, change):
    module = runner()
    from xml.etree import ElementTree as ET

    suite = ET.Element("testsuite")
    for path, name in module.PROBES.values():
        ET.SubElement(
            suite, "testcase", name=name, classname="tests." + Path(path).stem
        )
    first = suite[0]
    if change in {"failure", "error", "skip"}:
        ET.SubElement(first, "skipped" if change == "skip" else change)
    elif change == "missing":
        suite.remove(first)
    elif change == "duplicate":
        ET.SubElement(suite, "testcase", **first.attrib)
    elif change == "wrong-class":
        first.set("classname", "untrusted")
    elif change == "extra":
        ET.SubElement(suite, "testcase", name="other", classname="other")
    path = tmp_path / "junit.xml"
    ET.ElementTree(suite).write(path)
    result, unexpected = module.probe_results(path)
    accepted = not unexpected and all(probe["state"] == "PASSED" for probe in result)
    assert accepted == (change == "none")
    if change == "skip":
        assert result[0]["state"] == "SKIPPED"


def test_existing_report_refused_before_database_connection(tmp_path, monkeypatch):
    module = runner()
    tmp_path.chmod(0o700)
    output = tmp_path / "report"
    output.write_bytes(b"keep")
    monkeypatch.setattr(
        module, "create_engine", lambda *_a, **_k: pytest.fail("must not connect")
    )
    with pytest.raises(module.BackupError):
        module.run(admin_url="invalid", output=output)
    assert output.read_bytes() == b"keep"


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://host/postgres",
        "postgresql+psycopg://127.0.0.1/gw_preview_test",
    ],
)
def test_reject_nonlocal_or_preview_database_target(tmp_path, url):
    module = runner()
    tmp_path.chmod(0o700)
    with pytest.raises(module.BackupError):
        module.run(admin_url=url, output=tmp_path / "report")


@pytest.mark.parametrize(
    "change",
    ["none", "owner", "port", "host", "stopped", "missing-owner", "inspect-error"],
)
def test_restore_container_requires_matching_owned_loopback_target(monkeypatch, change):
    import json
    from types import SimpleNamespace

    from sqlalchemy.engine import make_url

    module = runner()
    info = {
        "owner": "synthetic-owner",
        "running": True,
        "ports": {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "55439"}]},
    }
    owner = "synthetic-owner"
    if change == "owner":
        info["owner"] = "someone-else"
    elif change == "port":
        info["ports"]["5432/tcp"][0]["HostPort"] = "5432"
    elif change == "host":
        info["ports"]["5432/tcp"][0]["HostIp"] = "0.0.0.0"
    elif change == "stopped":
        info["running"] = False
    elif change == "missing-owner":
        owner = None
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda *_a, **_kw: SimpleNamespace(
            returncode=1 if change == "inspect-error" else 0, stdout=json.dumps(info)
        ),
    )
    url = make_url("postgresql+psycopg://127.0.0.1:55439/postgres")
    if change == "none":
        module.validate_restore_container(url, "synthetic-container", owner)
    else:
        with pytest.raises(module.BackupError):
            module.validate_restore_container(url, "synthetic-container", owner)


def test_source_fingerprint_includes_untracked_fixed_probe(tmp_path, monkeypatch):
    module = runner()
    script = tmp_path / "tools/gw_route_verify.py"
    probe = tmp_path / "backend/tests/untracked_probe.py"
    script.parent.mkdir(parents=True)
    probe.parent.mkdir(parents=True)
    script.write_text("runner")
    probe.write_text("first probe")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "__file__", str(script))
    monkeypatch.setattr(
        module, "PROBES", {"FIXED": ("backend/tests/untracked_probe.py", "test_fixed")}
    )
    monkeypatch.setattr(
        module.subprocess,
        "check_output",
        lambda command, **_kw: b"a" * 40 if command[1] == "rev-parse" else b"",
    )
    before = module.source_identity()
    probe.write_text("changed probe")
    after = module.source_identity()
    assert before["commit"] == after["commit"]
    assert before["sourceDigest"] != after["sourceDigest"]
