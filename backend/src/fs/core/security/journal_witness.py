"""Authenticated delivery receipts. A filesystem receipt is not durability proof."""

import hashlib
import hmac
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from fs.core.backup import BackupError, private_directory, private_file
from fs.core.security.journal import ZERO, canonical, locked, verified_records, verify
from fs.core.security.journal_bundle import export, inspect, write

CONTEXT = b"FS-JOURNAL-DELIVERY-v1\0"
MAX_RECEIPTS = 10000


def read_store(directory, key):
    names = sorted(p.name for p in directory.iterdir() if p.name != ".lock")
    if len(names) > MAX_RECEIPTS:
        raise BackupError("전달 확인 기록 보관 한도를 확인하세요.")
    previous = ZERO
    result = []
    for sequence, name in enumerate(names, 1):
        if name != f"{sequence:010d}.json":
            raise BackupError("전달 확인 기록이 누락되었습니다.")
        path = private_file(directory / name)
        if path.stat().st_size > 4096:
            raise BackupError("전달 확인 기록 크기를 확인하세요.")
        raw = path.read_bytes()
        try:
            envelope = json.loads(raw)
            value = envelope["payload"]
            expected = hmac.new(
                key, CONTEXT + canonical(value), hashlib.sha256
            ).hexdigest()
            if set(envelope) != {"payload", "mac"} or not hmac.compare_digest(
                expected, envelope["mac"]
            ):
                raise ValueError()
            if (
                set(value)
                != {"version", "sequence", "previous", "head", "records", "verifiedAt"}
                or type(value["version"]) is not int
                or value["version"] != 1
                or type(value["sequence"]) is not int
                or value["sequence"] != sequence
                or value["previous"] != previous
                or type(value["records"]) is not int
                or not 0 <= value["records"] <= 100000
                or not isinstance(value["head"], str)
                or len(value["head"]) != 64
                or any(c not in "0123456789abcdef" for c in value["head"])
                or datetime.fromisoformat(value["verifiedAt"]).utcoffset() is None
            ):
                raise ValueError()
        except ValueError, TypeError, KeyError:
            raise BackupError("전달 확인 기록 인증에 실패했습니다.") from None
        previous = hashlib.sha256(raw).hexdigest()
        result.append({**value, "receiptDigest": previous})
    return result


def latest(directory, key, *, max_age=1800, minimum_sequence=1, now=None):
    if (
        type(max_age) is not int
        or not 1 <= max_age <= 86400
        or type(minimum_sequence) is not int
        or minimum_sequence < 1
    ):
        raise BackupError("전달 확인 기록의 시간/최소 순번 조건을 확인하세요.")
    with locked(directory) as root:
        values = read_store(root, key)
    if not values or values[-1]["sequence"] < minimum_sequence:
        raise BackupError("독립 보관한 최신 전달 확인 기록이 필요합니다.")
    value = values[-1]
    now = now or datetime.now(UTC)
    age = (now - datetime.fromisoformat(value["verifiedAt"])).total_seconds()
    if not 0 <= age <= max_age:
        raise BackupError("전달 확인 기록이 오래되었거나 시각이 잘못되었습니다.")
    return value


def publish(source, journal_key, expected_head, bundles, witness, witness_key):
    if len(witness_key) != 32 or hmac.compare_digest(journal_key, witness_key):
        raise BackupError("기록 키와 다른 별도32바이트 전달 확인 키가 필요합니다.")
    paths = [Path(p).resolve() for p in (source, bundles, witness)]
    if any(
        a.is_relative_to(b) or b.is_relative_to(a)
        for i, a in enumerate(paths)
        for b in paths[i + 1 :]
    ):
        raise BackupError(
            "원본·사본·전달 확인 기록은 겹치지 않는 별도 폴더여야 합니다."
        )
    private_directory(bundles)
    with locked(witness) as root:
        previous = read_store(root, witness_key)
        if len(previous) >= MAX_RECEIPTS:
            raise BackupError("전달 확인 기록 보관 한도에 도달했습니다.")
        if expected_head is None:
            if not previous:
                raise BackupError("첫 전달은 독립 최신 지문으로 시작해야 합니다.")
            expected_head = verify(source, journal_key)["head"]
        # Metadata only, for checking that delivery extends the witnessed prefix.
        state, records = verified_records(
            source, journal_key, expected_head, metadata_only=True
        )
        if previous:
            last = previous[-1]
            count = last["records"]
            prefix = records[count - 1]["digest"] if 0 < count <= len(records) else ZERO
            if count > len(records) or prefix != last["head"]:
                raise BackupError("이전 전달 확인 기록에서 이어지는 체인이 아닙니다.")
        sequence = len(previous) + 1
        bundle = Path(bundles) / f"{sequence:010d}-{expected_head}"
        export(source, journal_key, expected_head, bundle)
        copied = inspect(bundle, journal_key, expected_head)
        if copied != state:
            raise BackupError("전달 사본의 대조 결과가 다릅니다.")
        value = {
            "version": 1,
            "sequence": sequence,
            "previous": previous[-1]["receiptDigest"] if previous else ZERO,
            "head": state["head"],
            "records": state["records"],
            "verifiedAt": datetime.now(UTC).isoformat(),
        }
        envelope = {
            "payload": value,
            "mac": hmac.new(
                witness_key, CONTEXT + canonical(value), hashlib.sha256
            ).hexdigest(),
        }
        write(root / f"{sequence:010d}.json", canonical(envelope) + b"\n")
        fd = os.open(root, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        return {
            **value,
            "externalDurabilityConfirmed": False,
            "releaseAuthorized": False,
        }


def configured_head():
    directory = os.environ.get("FS_GW_JOURNAL_WITNESS_DIR")
    key_file = os.environ.get("FS_GW_JOURNAL_WITNESS_KEY_FILE")
    if directory is None and key_file is None:
        return None
    if not directory or not key_file:
        raise BackupError("전달 확인 기록 설정이 불완전합니다.")
    key = private_file(key_file, size=32).read_bytes()
    journal_file = os.environ.get("FS_GW_IDENTITY_JOURNAL_KEY_FILE")
    if journal_file and hmac.compare_digest(
        key, private_file(journal_file, size=32).read_bytes()
    ):
        raise BackupError("기록 키와 전달 확인 키를 분리하세요.")
    value = latest(
        directory,
        key,
        max_age=int(os.environ.get("FS_GW_JOURNAL_WITNESS_MAX_AGE_SECONDS", "1800")),
        minimum_sequence=int(os.environ.get("FS_GW_JOURNAL_WITNESS_MIN_SEQUENCE", "1")),
    )
    return value["head"]


def expected_head():
    witnessed = configured_head()
    manual = os.environ.get("FS_GW_JOURNAL_EXPECTED_HEAD")
    if witnessed is not None and manual is not None and manual != witnessed:
        raise BackupError("독립 전달 확인 지문과 수동 지문이 다릅니다.")
    return witnessed if witnessed is not None else (manual or "")
