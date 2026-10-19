"""Offline journal boundary planning. No permission grants and no source DB writes."""

import re

from fs.core.backup import BackupError
from fs.core.security.journal import MAX_TOTAL_RECORDS, ZERO, verified_records
from fs.core.security.journal_witness import expected_head
from fs.core.security.recording import configured
from fs.core.security.transaction_proof import classify
from fs.gw.security_journal import confirmed_digests


def source_records():
    config = configured()
    if config is None:
        return None
    expected = expected_head()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise BackupError("별도 보관한 최신 변경 기록 지문이 필요합니다.")
    return verified_records(config[0], config[1], expected, metadata_only=True)


def anchor(c, observed):
    if observed is None:
        return None
    state, records = observed
    return {
        "version": 1,
        "head": state["head"],
        "records": len(records),
        "confirmed": sorted(confirmed_digests(c, records)),
    }


def plan(c, baseline, observed):
    if baseline is None and observed is None:
        return None
    if baseline is None or observed is None:
        raise BackupError("같은 변경 기록 설정으로 새 백업과 권한 대조를 준비하세요.")
    state, records = observed
    count = baseline["records"]
    if type(count) is not int or not 0 <= count <= len(records):
        raise BackupError("백업 기준 이후 변경 기록이 누락되었습니다.")
    prefix = records[count - 1]["digest"] if count else ZERO
    if prefix != baseline["head"]:
        raise BackupError("백업 기준과 변경 기록의 연속성이 다릅니다.")
    prefix_digests = {r["digest"] for r in records[:count]}
    baseline_confirmed = set(baseline["confirmed"])
    if not baseline_confirmed <= prefix_digests:
        raise BackupError("백업 기준의 DB 대조 기록이 잘못되었습니다.")
    # Includes intents written before the backup snapshot but not visible in that DB snapshot.
    candidates = [r for r in records if r["digest"] not in baseline_confirmed]
    current_confirmed = confirmed_digests(c, records)
    dispositions = classify(c, candidates, current_confirmed)
    aborted = sum(v == "ABORT_CONFIRMED" for v in dispositions.values())
    candidates = [
        r for r in candidates if dispositions[r["digest"]] != "ABORT_CONFIRMED"
    ]
    users, scopes = set(), set()
    counters = 0
    for record in candidates:
        payload = record["payload"]
        kind = payload["coverage"]
        if kind in {"core.security.intent.v1", "hr.users.intent.v1"}:
            uid = payload["userId"]
            if uid is None:
                counters += 1
            else:
                users.add(uid)
        if kind in {"gw.company.intent.v2", "gw.company_identity.intent.v1"}:
            scope = (payload.get("workspaceId"), payload.get("generationId"))
            if any(type(v) is not int or v <= 0 for v in scope):
                raise BackupError("과거 변경 기록의 회사 범위를 확인할 수 없습니다.")
            scopes.add(scope)
    return {
        "version": 1,
        "baseHead": baseline["head"],
        "baseRecords": count,
        "head": state["head"],
        "records": len(records),
        "candidates": len(candidates),
        "unconfirmed": sum(r["digest"] not in current_confirmed for r in candidates),
        "counterIntents": counters,
        "abortedIntents": aborted,
        "users": sorted(users),
        "scopes": [list(s) for s in sorted(scopes)],
        "completenessConfirmed": False,
    }


def validate_restore(baseline, restrictions):
    if baseline is None and restrictions is None:
        return
    if baseline is None or restrictions is None:
        raise BackupError("변경 기록과 권한 대조 연결이 누락되었습니다.")
    if (
        baseline.get("version") != 1
        or restrictions.get("version") != 1
        or restrictions.get("baseHead") != baseline["head"]
        or restrictions.get("baseRecords") != baseline["records"]
        or restrictions.get("head") != expected_head()
        or not re.fullmatch(r"[0-9a-f]{64}", restrictions.get("head", ""))
    ):
        raise BackupError("별도 최신 변경 기록 지문과 권한 대조 파일이 다릅니다.")
    for key in (
        "records",
        "baseRecords",
        "candidates",
        "unconfirmed",
        "counterIntents",
    ):
        if (
            type(restrictions.get(key)) is not int
            or not 0 <= restrictions[key] <= MAX_TOTAL_RECORDS
        ):
            raise BackupError("변경 기록 대조 건수가 잘못되었습니다.")
    if (
        type(restrictions.get("abortedIntents", 0)) is not int
        or not 0 <= restrictions.get("abortedIntents", 0) <= restrictions["records"]
    ):
        raise BackupError("롤백 판정 건수가 잘못되었습니다.")
    if (
        restrictions["baseRecords"] > restrictions["records"]
        or restrictions["candidates"] > restrictions["records"]
        or restrictions["unconfirmed"] > restrictions["candidates"]
        or restrictions["counterIntents"] > restrictions["candidates"]
    ):
        raise BackupError("변경 기록 대조 범위가 잘못되었습니다.")
    for uid in restrictions["users"]:
        if type(uid) is not int or uid <= 0:
            raise BackupError("격리 대상 계정 식별자가 잘못되었습니다.")
    for scope in restrictions["scopes"]:
        if len(scope) != 2 or any(type(v) is not int or v <= 0 for v in scope):
            raise BackupError("격리 대상 회사 범위가 잘못되었습니다.")
