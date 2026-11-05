"""Immutable source exports for historical integration fixtures; no other checkout."""

import subprocess
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

ROOT = Path(__file__).resolve().parents[2]
PINS = {
    "4c898ac": "4c898aca0d4a56c9fb91a4d1b89a5b5b06a718e0",
    "783a2c1": "783a2c1aa6e4f0053d055341f9738226a60dbdc7",
}


@pytest.fixture
def pinned_source():
    directory = ROOT / "work/gw-integration-pins"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with ExitStack() as stack:

        def export(pin):
            if pin not in PINS:
                raise ValueError("fixed integration pin required")
            source = Path(
                stack.enter_context(TemporaryDirectory(prefix=pin + "-", dir=directory))
            )
            archive = subprocess.run(
                [
                    "git",
                    "archive",
                    PINS[pin],
                    "backend",
                    "tools",
                    "docs/db/schema-metadata",
                ],
                cwd=ROOT,
                capture_output=True,
                check=True,
            ).stdout
            subprocess.run(["tar", "-x", "-C", str(source)], input=archive, check=True)
            return source

        yield export
