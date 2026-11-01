"""TOU 시간대별 요금의 코드 상수와 구간 검증 (DSN-15 Q1).

계절 월 구분은 한국 산업용 전력 요금제를 따른다. **표가 아니라 규칙이라 DB에 두지 않는다**
(FS-013 D6 — 정적 기준은 리포지토리 파일). 요율 자체는 사업장마다 다르므로 DB(`fems.tariff_band`)에 둔다.

부하 구분(경부하·중간부하·최대부하)도 구간마다 담당자가 고른다 — 나라·계약 종별마다 시간이
달라서 코드로 박으면 거짓이 된다. 여기서 강제하는 것은 **구간이 하루를 빈틈·겹침 없이 덮는가**뿐이다.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Any

SUMMER, SPRING_FALL, WINTER = "SUMMER", "SPRING_FALL", "WINTER"
WEEKDAY, SATURDAY, HOLIDAY = "WEEKDAY", "SATURDAY", "HOLIDAY"
OFF_PEAK, MID, PEAK = "OFF_PEAK", "MID", "PEAK"

SEASONS = (SUMMER, SPRING_FALL, WINTER)
DAY_KINDS = (WEEKDAY, SATURDAY, HOLIDAY)
LOAD_BANDS = (OFF_PEAK, MID, PEAK)

SEASON_LABEL = {SUMMER: "여름", SPRING_FALL: "봄·가을", WINTER: "겨울"}
DAY_KIND_LABEL = {WEEKDAY: "평일", SATURDAY: "토요일", HOLIDAY: "휴일"}
LOAD_BAND_LABEL = {OFF_PEAK: "경부하", MID: "중간부하", PEAK: "최대부하"}

# 여름 6~8월, 겨울 11~2월, 나머지가 봄·가을.
_SEASON_BY_MONTH = {
    **{m: SUMMER for m in (6, 7, 8)},
    **{m: WINTER for m in (11, 12, 1, 2)},
    **{m: SPRING_FALL for m in (3, 4, 5, 9, 10)},
}

HOURS_IN_DAY = 24


def season_of(month: int) -> str:
    """달(1~12) → 계절."""
    return _SEASON_BY_MONTH[month]


def day_kind_of(day: date, holidays: Iterable[date]) -> str:
    """날짜 → 요일 구분. 휴일이 토요일보다 세다 — 휴일에는 토요일 요율을 쓰지 않는다."""
    if day in set(holidays):
        return HOLIDAY
    if day.weekday() == 6:  # 일요일은 공휴일 목록에 없어도 휴일이다
        return HOLIDAY
    if day.weekday() == 5:
        return SATURDAY
    return WEEKDAY


def coverage_errors(bands: list[dict[str, Any]]) -> list[str]:
    """구간이 계절·요일마다 0~24시를 빈틈·겹침 없이 덮는지 본다. 사람이 읽을 오류 문장.

    DB CHECK는 구간 하나의 모양(0 ≤ from < to ≤ 24)까지만 본다. 구간 **사이**의 빈틈과 겹침은
    여러 행을 함께 봐야 알 수 있어 서비스가 지킨다(`fems.tariff_band` SERVICE/DB_POLICY).
    """
    errors: list[str] = []
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for band in bands:
        grouped.setdefault((band["season"], band["day_kind"]), []).append(band)

    for season in SEASONS:
        for day_kind in DAY_KINDS:
            where = f"{SEASON_LABEL[season]}·{DAY_KIND_LABEL[day_kind]}"
            rows = sorted(
                grouped.get((season, day_kind), []), key=lambda b: b["hour_from"]
            )
            if not rows:
                errors.append(f"{where} 구간이 없습니다.")
                continue
            cursor = 0
            for row in rows:
                start, end = row["hour_from"], row["hour_to"]
                if start > cursor:
                    errors.append(f"{where} {cursor}~{start}시가 비어 있습니다.")
                elif start < cursor:
                    errors.append(f"{where} {start}~{cursor}시가 겹칩니다.")
                cursor = max(cursor, end)
            if cursor < HOURS_IN_DAY:
                errors.append(f"{where} {cursor}~{HOURS_IN_DAY}시가 비어 있습니다.")
    return errors


def rate_lookup(bands: list[dict[str, Any]]) -> dict[tuple[str, str, int], dict]:
    """(계절, 요일, 시) → 그 시간의 구간. 시간별 사용량에 요율을 붙일 때 쓴다."""
    table: dict[tuple[str, str, int], dict] = {}
    for band in bands:
        for hour in range(band["hour_from"], band["hour_to"]):
            table[(band["season"], band["day_kind"], hour)] = band
    return table
