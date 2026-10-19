"""Diagnostic handoff only; no review acknowledgement grants access."""

import os
from datetime import UTC, datetime
from pathlib import Path

from fs.core.backup import BackupError, create_private
from fs.core.security.journal import canonical
from fs.core.security.transaction_proof import summary

GUIDANCE = {
    "AUDIT_CONFIRMED": (
        "DB 반영 확인",
        "백업 기준과 이후 변경을 새 checkpoint에서 대조하세요.",
    ),
    "ABORT_CONFIRMED": (
        "전체 거래 취소 확인",
        "새 checkpoint와 새 격리 복원에서만 제외 결과를 확인하세요.",
    ),
    "PENDING": (
        "거래 처리 중",
        "원본 거래가 끝난 뒤 최신 지문으로 다시 점검하세요. 제한을 유지하세요.",
    ),
    "SOURCE_MISMATCH": (
        "원본 근거 불일치",
        "원본 DB·타임라인과 복구 이력을 확인하세요. 제한을 유지하세요.",
    ),
    "COMMITTED_WITHOUT_AUDIT": (
        "확정 거래의 감사 표식 없음",
        "저장점 취소·감사 누락을 조사하세요. 전체 취소로 간주하지 마세요.",
    ),
    "UNKNOWN": (
        "판정 근거 부족",
        "과거 기록·거래 상태 보존 범위와 원본 감사를 확인하세요. 추정으로 제외하지 마세요.",
    ),
}


def build(state, records, dispositions):
    digests = [r["digest"] for r in records]
    if (
        len(set(digests)) != len(digests)
        or set(digests) != set(dispositions)
        or any(v not in GUIDANCE for v in dispositions.values())
    ):
        raise BackupError("점검 기록과 거래 판정 범위가 다릅니다.")
    return {
        "kind": "GW_JOURNAL_REVIEW_DIAGNOSTIC",
        "version": 1,
        "observedAt": datetime.now(UTC).isoformat(),
        "head": state["head"],
        "records": len(records),
        **summary(dispositions),
        "releaseAuthorized": False,
        "checkpointInput": False,
        "coverage": "지정 지문까지의 기록만 대조. 이후 변경·전체 누락 없음·현재 권한 전체는 확인하지 않음.",
        "items": [
            {
                "digest": digest,
                "disposition": dispositions[digest],
                "finding": GUIDANCE[dispositions[digest]][0],
                "nextAction": GUIDANCE[dispositions[digest]][1],
            }
            for digest in digests
        ],
        "operatorChecks": [
            "점검 지문·시각·담당자와 별도 보관 근거의 위치를 운영 기록에 남기세요. 비밀번호·개인정보는 첨부하지 마세요.",
            "미확인은 확인 불가로 기록하고 관련 계정·회사 제한을 유지하세요. 검토 완료를 취소 확인으로 바꾸지 마세요.",
            "원본 감사와 변경 경로를 조사하고 부족한 수집은 수정 후 합성 검증하세요. 과거 파일에 근거를 소급하지 마세요.",
            "최신 지문으로 새 checkpoint·새 격리 복원 보고를 대조하세요. 기존 제한 복원본을 직접 열지 마세요.",
            "관리자·직원 업무와 회수 계정 거부, 외부 사본·복구 조건을 별도로 인수하세요. 이 보고서는 운영 재개 승인이 아닙니다.",
        ],
    }


def write(path, report):
    # Never overwrite an earlier review or follow a destination symlink.
    with create_private(path) as out:
        out.write(canonical(report) + b"\n")
        out.flush()
        os.fsync(out.fileno())
    fd = os.open(Path(path).parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
