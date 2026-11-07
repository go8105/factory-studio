"""core 읽기 전용 조회 인터페이스 (DSN-16 Q1 · 6장).

휴일 달력은 회사 공통 정보라 core가 가진다. 업무 솔루션(BEMS 스케줄, FEMS TOU, MES 근무조, HR 근태)은
**FK 없이 날짜로만** 읽는다(FS-013 §6). core는 끌 수 있는 솔루션이 아니라 None을 돌려주지 않는다.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import Connection, text

from fs.common.auth import AuthContext


def holidays(
    connection: Connection, scoped: AuthContext, date_from: date, date_to: date
) -> list[dict[str, Any]]:
    """기간(양끝 포함)의 휴일 `[{date, name, kind}]`, 날짜 오름차순. kind는 PUBLIC(공휴일)·COMPANY(회사 휴무).

    일요일은 목록에 없어도 휴일이다 — 요일 구분(휴일 > 토 > 평일)은 읽는 쪽이 정한다.
    """
    rows = connection.execute(
        text(
            "SELECT holiday_on, name, kind FROM core.holiday "
            "WHERE workspace_id=:w AND generation_id=:g AND holiday_on BETWEEN :date_from AND :date_to "
            "ORDER BY holiday_on"
        ),
        {
            "w": scoped.workspace_id,
            "g": scoped.generation_id,
            "date_from": date_from,
            "date_to": date_to,
        },
    ).mappings()
    return [
        {"date": r["holiday_on"].isoformat(), "name": r["name"], "kind": r["kind"]}
        for r in rows
    ]
