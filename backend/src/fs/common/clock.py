"""업무 기준일(KST). 게스트 복사·세대 초기화의 T로 쓴다.

FS_TODAY(YYYY-MM-DD)를 주면 그 날짜를 쓴다. 테스트·브라우저 스모크가 템플릿 기준일과 맞추려고 쓴다.
운영 .env에는 넣지 않는다(넣으면 모든 새 공간이 그 날짜 기준 데이터가 된다).
"""

from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


def real_today() -> date:
    """실제 KST 날짜. 만료처럼 사람의 시간에 묶인 값은 이것을 쓴다(FS_TODAY 영향 없음)."""
    return datetime.now(ZoneInfo("Asia/Seoul")).date()


def business_today() -> date:
    """데이터 기준일 T. FS_TODAY가 있으면 그 날짜, 없으면 실제 KST 날짜."""
    override = os.environ.get("FS_TODAY")
    if override:
        return date.fromisoformat(override)
    return real_today()


def guest_expires_at() -> datetime:
    """게스트 만료 = 실제 생성일 다음 날 00:00 KST. 데이터 기준일을 고정해도 만료는 실제 시간을 따른다."""
    return datetime.combine(
        real_today() + timedelta(days=1), time(0), ZoneInfo("Asia/Seoul")
    )
