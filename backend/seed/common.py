from __future__ import annotations
# ruff: noqa: I001, FURB157, PYI041

import json
from calendar import monthrange
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from zoneinfo import ZoneInfo

SEED_VERSION = "sv-20260928-1"  # FS-025c: BEMS 시드 +4,218행
SEOUL = ZoneInfo("Asia/Seoul")
CODEBOOK_PATH = Path(__file__).with_name("codebook.json")


def codebook() -> dict[str, object]:
    """세 솔루션이 공유하는 유일한 코드 사전 입력점이다."""
    return json.loads(CODEBOOK_PATH.read_text(encoding="utf-8"))


def month_shift(value: date, months: int) -> date:
    index = value.year * 12 + value.month - 1 + months
    year, month0 = divmod(index, 12)
    return date(year, month0 + 1, min(value.day, monthrange(year, month0 + 1)[1]))


def month_text(value: date, months: int = 0) -> str:
    shifted = month_shift(value, months)
    return f"{shifted.year:04d}-{shifted.month:02d}"


def month_mondays(value: date, months: int = 0) -> list[str]:
    shifted = month_shift(value.replace(day=1), months)
    mondays = [
        shifted.replace(day=day)
        for day in range(1, 22)
        if shifted.replace(day=day).weekday() == 0
    ]
    return [
        f"{day.isocalendar().year:04d}-W{day.isocalendar().week:02d}" for day in mondays
    ]


def at(seed_date: date, day: int, hour: int = 0, minute: int = 0) -> datetime:
    local = datetime.combine(seed_date + timedelta(days=day), time(hour, minute), SEOUL)
    return local.astimezone(UTC)


def calendar_date(seed_date: date, day: int) -> date:
    return seed_date + timedelta(days=day)


def decimal(value: str | int | float, places: str = "0.001") -> Decimal:
    return Decimal(str(value)).quantize(Decimal(places), rounding=ROUND_HALF_UP)


def round_half_up(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


# 에너지 목표 = 해당 월 실적 × 비율 (FS-005g 5.5, sv-20260924-2).
# 난수 대신 고정 표다. 90~105% 범위에서 월·대상마다 달라 달성(≥1.00)과 초과(<1.00)가 섞인다.
# 값: (M−1 비율, M0 비율). SITE는 에너지원 코드와 TOE, EQUIPMENT는 설비 코드.
TARGET_RATIOS: dict[str, tuple[Decimal, Decimal]] = {
    "ELEC": (Decimal("0.97"), Decimal("1.02")),
    "GAS": (Decimal("0.93"), Decimal("0.98")),
    "WATER": (Decimal("1.05"), Decimal("0.95")),
    "TOE": (Decimal("0.96"), Decimal("1.01")),
    "INJ-01": (Decimal("1.03"), Decimal("0.97")),
    "INJ-02": (Decimal("0.92"), Decimal("1.05")),
    "INJ-03": (Decimal("0.98"), Decimal("0.94")),
    "ASM-01": (Decimal("1.00"), Decimal("1.02")),
    "ASM-02": (Decimal("0.95"), Decimal("0.90")),
    "ASM-03": (Decimal("1.04"), Decimal("0.99")),
    "INS-01": (Decimal("0.91"), Decimal("0.96")),
    "INS-02": (Decimal("1.01"), Decimal("1.00")),  # M0은 미설정(5.5)이라 쓰지 않는다
}


def target_ratio(key: str, month_offset: int) -> Decimal:
    return TARGET_RATIOS[key][0 if month_offset == -1 else 1]


def equipment_ratio_sql(seed_date: date) -> str:
    """검증용 VALUES 목록 (설비 코드, 목표 월, 비율). 상수만 넣으므로 바인딩 없이 쓴다."""
    rows = [
        f"('{code}','{month_text(seed_date, offset)}',{target_ratio(code, offset)})"
        for code in TARGET_RATIOS
        if "-" in code
        for offset in (-1, 0)
    ]
    return ",".join(rows)
