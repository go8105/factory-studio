from __future__ import annotations
# ruff: noqa: I001, FURB157, PYI041

import json
from calendar import monthrange
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from zoneinfo import ZoneInfo

SEED_VERSION = "sv-20260924-1"
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
