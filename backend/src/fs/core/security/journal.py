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
MAX_TOTAL_RECORDS = 100000
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


def record_paths(directory):
    """Flatten a preserved prefix and its active suffix without renumbering."""
    names = {p.name for p in directory.iterdir()} - {".lock"}
    base = 0
    archived = []
    prefix_head = ZERO
    if ".history.json" in names or ".history" in names:
        if not {".history.json", ".history"} <= names:
            raise BackupError("보존 기록 연결이 누락되었습니다.")
        manifest = private_file(directory / ".history.json")
        if manifest.stat().st_size > 4096:
            raise BackupError("보존 기록 명세 크기를 확인하세요.")
        try:
            value = json.loads(manifest.read_bytes())
            base = value["records"]
            prefix_head = value["head"]
            if (
                set(value) != {"kind", "version", "records", "head"}
                or value["kind"] != "GW_JOURNAL_PRESERVED_PREFIX"
                or type(value["version"]) is not int
                or value["version"] != 1
                or type(base) is not int
                or not 1 <= base <= MAX_TOTAL_RECORDS
                or not isinstance(prefix_head, str)
                or not re.fullmatch(r"[0-9a-f]{64}", prefix_head)
            ):
                raise ValueError()
        except ValueError, KeyError, TypeError:
            raise BackupError("보존 기록 명세를 확인하세요.") from None
        history = private_directory(directory / ".history")
        history_names = sorted(p.name for p in history.iterdir())
        if history_names != [f"{n:010d}.json" for n in range(1, base + 1)]:
            raise BackupError("보존 기록이 누락되었거나 알 수 없는 파일이 있습니다.")
        archived = [history / name for name in history_names]
        names -= {".history.json", ".history"}
    active = sorted(names)
    if len(active) > MAX_RECORDS or base + len(active) > MAX_TOTAL_RECORDS:
        raise BackupError("기록 보관 한도를 확인하세요.")
    if active != [f"{n:010d}.json" for n in range(base + 1, base + len(active) + 1)]:
        raise BackupError("보안 변경 기록이 누락되었거나 알 수 없는 파일이 있습니다.")
    return archived + [directory / name for name in active], base, prefix_head


def _verify(directory, key, expected_head=None, records=None, metadata_only=False):
    paths, base, prefix_head = record_paths(directory)
    previous = ZERO
    coverages = set()
    for sequence, path in enumerate(paths, 1):
        path = private_file(path)
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
            if "transactionProof" in payload:
                proof = payload["transactionProof"]
                if (
                    not isinstance(proof, dict)
                    or proof.get("version") != 1
                    or not isinstance(proof.get("sourceIdentity"), str)
                    or not re.fullmatch(r"[0-9a-f]{64}", proof["sourceIdentity"])
                    or not isinstance(proof.get("timeline"), str)
                    or not re.fullmatch(r"[0-9A-F]{8}", proof["timeline"])
                    or not isinstance(proof.get("transactionId"), str)
                    or not re.fullmatch(r"[1-9][0-9]{0,19}", proof["transactionId"])
                    or int(proof["transactionId"]) >= 2**64
                ):
                    raise ValueError()
            if payload["coverage"] not in {
                "gw.company_identity.intent.v1",
                "gw.company.intent.v2",
                "core.security.intent.v1",
                "hr.users.intent.v1",
            }:
                raise ValueError()
            if payload["coverage"] in {
                "gw.company.intent.v2",
                "hr.users.intent.v1",
            } and (
                any(
                    type(payload[k]) is not int or payload[k] <= 0
                    for k in ("workspaceId", "generationId")
                )
                or not isinstance(payload["operation"], str)
                or not 1 <= len(payload["operation"]) <= 200
                or not isinstance(payload["snapshot"], dict)
            ):
                raise ValueError()
            if payload["coverage"] in {
                "core.security.intent.v1",
                "hr.users.intent.v1",
            } and (
                (
                    payload["userId"] is not None
                    and (type(payload["userId"]) is not int or payload["userId"] <= 0)
                )
                or (
                    payload["coverage"] == "hr.users.intent.v1"
                    and payload["userId"] is None
                )
                or not isinstance(payload["operation"], str)
                or not 1 <= len(payload["operation"]) <= 200
                or not isinstance(payload["snapshot"], dict)
            ):
                raise ValueError()
        except InvalidTag, ValueError, KeyError, TypeError:
            raise BackupError("보안 변경 기록 인증에 실패했습니다.") from None
        coverages.add(payload["coverage"])
        previous = hashlib.sha256(raw).hexdigest()
        if sequence == base and previous != prefix_head:
            raise BackupError("보존 기록의 끝 지문이 다릅니다.")
        if records is not None:
            if metadata_only:
                payload = {
                    k: v
                    for k, v in payload.items()
                    if k
                    in {
                        "coverage",
                        "operation",
                        "userId",
                        "workspaceId",
                        "generationId",
                        "transactionProof",
                    }
                }
            records.append({"digest": previous, "payload": payload})
    if expected_head is not None and (
        not re.fullmatch(r"[0-9a-f]{64}", expected_head) or expected_head != previous
    ):
        raise BackupError("별도로 보관한 최신 지문과 일치하지 않습니다.")
    return {
        "records": len(paths),
        "head": previous,
        "coverage": next(iter(coverages))
        if len(coverages) == 1
        else "mixed"
        if coverages
        else "empty",
        "completenessConfirmed": False,
        "commitsConfirmed": False,
    }


def verify(path, key, expected_head=None):
    with locked(path) as directory:
        return _verify(directory, key, expected_head)


def verified_records(path, key, expected_head, *, metadata_only=False):
    """Operator-only internal interface; never print decrypted payloads."""
    with locked(path) as directory:
        records = []
        state = _verify(directory, key, expected_head, records, metadata_only)
        return state, records


def append(path, key, payload):
    with locked(path) as directory:
        state = _verify(directory, key)
        _, base, _ = record_paths(directory)
        if (
            state["records"] - base >= MAX_RECORDS
            or state["records"] >= MAX_TOTAL_RECORDS
        ):
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
