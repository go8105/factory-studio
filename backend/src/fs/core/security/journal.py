"""Private encrypted intent chain. A valid chain does not prove DB commit or coverage."""

import fcntl
import hashlib
import json
import os
import re
from contextlib import contextmanager

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from fs.core.backup import BackupError, create_private, private_directory, private_file

ZERO = "0" * 64
MAX_RECORDS = 10000
MAX_RECORD_BYTES = 4 * 1024 * 1024


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


@contextmanager
def locked(directory):
    directory = private_directory(directory)
    fd = os.open(directory / ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        private_file(directory / ".lock")
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield directory
    finally:
        os.close(fd)


def _verify(directory, key, expected_head=None):
    names = sorted(p.name for p in directory.iterdir() if p.name != ".lock")
    if len(names) > MAX_RECORDS:
        raise BackupError("기록 보관 한도를 확인하세요.")
    previous = ZERO
    for sequence, name in enumerate(names, 1):
        if name != f"{sequence:010d}.json":
            raise BackupError(
                "보안 변경 기록이 누락되었거나 알 수 없는 파일이 있습니다."
            )
        path = private_file(directory / name)
        if path.stat().st_size > MAX_RECORD_BYTES:
            raise BackupError("보안 변경 기록 크기를 확인하세요.")
        raw = path.read_bytes()
        try:
            record = json.loads(raw)
            header = {"version": 1, "sequence": sequence, "previous": previous}
            if record["header"] != header:
                raise ValueError()
            plain = AESGCM(key).decrypt(
                bytes.fromhex(record["nonce"]),
                bytes.fromhex(record["ciphertext"]),
                canonical(header),
            )
            payload = json.loads(plain)
            if payload["coverage"] != "gw.company_identity.intent.v1":
                raise ValueError()
        except InvalidTag, ValueError, KeyError, TypeError:
            raise BackupError("보안 변경 기록 인증에 실패했습니다.") from None
        previous = hashlib.sha256(raw).hexdigest()
    if expected_head is not None and (
        not re.fullmatch(r"[0-9a-f]{64}", expected_head) or expected_head != previous
    ):
        raise BackupError("별도로 보관한 최신 지문과 일치하지 않습니다.")
    return {
        "records": len(names),
        "head": previous,
        "coverage": "gw.company_identity.intent.v1",
        "completenessConfirmed": False,
        "commitsConfirmed": False,
    }


def verify(path, key, expected_head=None):
    with locked(path) as directory:
        return _verify(directory, key, expected_head)


def append(path, key, payload):
    with locked(path) as directory:
        state = _verify(directory, key)
        if state["records"] >= MAX_RECORDS:
            raise BackupError("보안 변경 기록 보관 한도에 도달했습니다.")
        header = {
            "version": 1,
            "sequence": state["records"] + 1,
            "previous": state["head"],
        }
        nonce = os.urandom(12)
        raw = canonical(
            {
                "header": header,
                "nonce": nonce.hex(),
                "ciphertext": AESGCM(key)
                .encrypt(nonce, canonical(payload), canonical(header))
                .hex(),
            }
        )
        if len(raw) > MAX_RECORD_BYTES:
            raise BackupError("보안 변경 기록 크기 한도를 초과했습니다.")
        # A partial file is deliberately retained: the next operation must fail closed.
        with create_private(directory / f"{header['sequence']:010d}.json") as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        return hashlib.sha256(raw).hexdigest()
