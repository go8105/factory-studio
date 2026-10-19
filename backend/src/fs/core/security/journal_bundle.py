"""Immutable encrypted snapshot export; does not rotate or truncate the source."""

import json
import os
from pathlib import Path

from fs.core.backup import BackupError, create_private, private_directory, private_file
from fs.core.security.journal import _verify, canonical, locked, verify


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write(path, data):
    with create_private(path) as out:
        out.write(data)
        out.flush()
        os.fsync(out.fileno())


def export(source, key, expected_head, destination):
    destination = Path(destination)
    private_directory(destination.parent)
    source = Path(source)
    if destination.resolve().is_relative_to(source.resolve()):
        raise BackupError("보관 묶음은 원본 기록 폴더 밖에 만드세요.")
    with locked(source) as directory:
        state = _verify(directory, key, expected_head)
        # A partial destination is retained on failure and cannot be overwritten.
        destination.mkdir(mode=0o700)
        sync_directory(destination.parent)
        records = destination / "records"
        records.mkdir(mode=0o700)
        for number in range(1, state["records"] + 1):
            name = f"{number:010d}.json"
            write(records / name, private_file(directory / name).read_bytes())
        sync_directory(records)
        copied = verify(records, key, expected_head)
        if copied != state:
            raise BackupError("복사한 기록 묶음의 대조 결과가 다릅니다.")
        manifest = {
            "kind": "GW_ENCRYPTED_JOURNAL_BUNDLE",
            "version": 1,
            "head": state["head"],
            "records": state["records"],
        }
        # Written last; absence means incomplete export.
        write(destination / "manifest.json", canonical(manifest) + b"\n")
        sync_directory(destination)
        sync_directory(destination.parent)
        return state


def inspect(path, key, expected_head):
    path = private_directory(path)
    if {p.name for p in path.iterdir()} != {"manifest.json", "records"}:
        raise BackupError("기록 묶음이 미완료이거나 알 수 없는 파일이 있습니다.")
    manifest_file = private_file(path / "manifest.json")
    if manifest_file.stat().st_size > 4096:
        raise BackupError("기록 묶음 명세 크기를 확인하세요.")
    try:
        manifest = json.loads(manifest_file.read_bytes())
    except ValueError, TypeError:
        raise BackupError("기록 묶음 명세를 확인하세요.") from None
    state = verify(path / "records", key, expected_head)
    expected = {
        "kind": "GW_ENCRYPTED_JOURNAL_BUNDLE",
        "version": 1,
        "head": state["head"],
        "records": state["records"],
    }
    if manifest != expected or type(manifest.get("records")) is not int:
        raise BackupError("기록 묶음 명세와 독립 지문 대조 결과가 다릅니다.")
    return state
