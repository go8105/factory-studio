"""Explicitly install synthetic operator settings in each test-owned trust store."""

import os
from pathlib import Path

from fs.gw import catalog_trust_store as floor
from fs.gw.evidence_trust import configured_environment


def approve_environment(monkeypatch, directory=None):
    if directory is not None:
        directory = Path(directory)
        directory.mkdir(mode=0o700, exist_ok=True)
        monkeypatch.setenv(floor.ENV, str(directory))
    directory = Path(os.environ[floor.ENV])
    initialized = (directory / floor.HEAD).exists()
    sha = floor.inspect(directory)[1] if initialized else "ABSENT"
    return floor.commit(
        directory,
        configured_environment(),
        expected_digest=sha,
        initialize=not initialized,
    )


def approve_subprocess(env):
    import subprocess
    import sys

    directory = Path(env[floor.ENV])
    initialized = (directory / floor.HEAD).exists()
    sha = floor.inspect(directory)[1] if initialized else "ABSENT"
    result = subprocess.run(
        [
            sys.executable,
            "tools/gw_catalog_trust.py",
            "advance" if initialized else "initialize",
            "--expected-digest",
            sha,
        ],
        env=env,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, "synthetic trust installation failed"
