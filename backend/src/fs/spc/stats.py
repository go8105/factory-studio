"""SPC 계산 (FS-028 모듈 설계 5장). 부동소수 오차로 한계 경계 판정이 흔들리지 않게 Decimal만 쓴다.

부분군 크기는 5로 고정(D39, 13장 1)이지만 상수는 표로 둔다 — n을 늘릴 때 표만 늘린다.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal
from itertools import pairwise

CONSTANTS = {
    5: {
        "A2": Decimal("0.577"),
        "D3": Decimal(0),
        "D4": Decimal("2.114"),
        "d2": Decimal("2.326"),
    }
}
MIN_BASIS = 20  # 한계 게시·공정능력 최소 유효 부분군(D40, 13장 5)
RUN_LENGTH = 9  # 규칙 2: 중심선 한쪽 연속 9점
TREND_LENGTH = 6  # 규칙 3: 연속 6점 증가 또는 감소
_Q = Decimal("0.000001")


def q(value: Decimal) -> Decimal:
    """numeric(14,6) 저장 전 반올림(ROUND_HALF_UP)."""
    return value.quantize(_Q, rounding=ROUND_HALF_UP)


def mean(values: Sequence[Decimal]) -> Decimal:
    return sum(values, Decimal(0)) / len(values)


def subgroup(values: Sequence[Decimal]) -> tuple[Decimal, Decimal]:
    """(X̄, R)."""
    return q(mean(values)), q(max(values) - min(values))


def limits(
    xbars: Sequence[Decimal], ranges: Sequence[Decimal], n: int = 5
) -> dict[str, Decimal]:
    k = CONSTANTS[n]
    x_cl, r_cl = mean(xbars), mean(ranges)
    return {
        "xbar_cl": q(x_cl),
        "xbar_ucl": q(x_cl + k["A2"] * r_cl),
        "xbar_lcl": q(x_cl - k["A2"] * r_cl),
        "r_cl": q(r_cl),
        "r_ucl": q(k["D4"] * r_cl),
        "r_lcl": q(k["D3"] * r_cl),
    }


def signals(
    previous_xbars: Sequence[Decimal],
    xbar: Decimal,
    r: Decimal,
    limit: dict[str, Decimal],
) -> list[tuple[str, int, Decimal]]:
    """규칙 1~3 판정. previous_xbars는 같은 한계 버전의 이전 유효 부분군 X̄(오래된 → 최근).

    연속 판정은 버전마다 새로 센다(13장 3) — 호출자가 같은 버전 부분군만 넘긴다.
    조건이 이어지는 동안 점마다 이상을 기록한다(관리도 표기와 같다).
    """
    found: list[tuple[str, int, Decimal]] = []
    if xbar > limit["xbar_ucl"] or xbar < limit["xbar_lcl"]:
        found.append(("XBAR", 1, xbar))
    if r > limit["r_ucl"] or r < limit["r_lcl"]:
        found.append(("R", 1, r))
    run = [*previous_xbars[-(RUN_LENGTH - 1) :], xbar]
    cl = limit["xbar_cl"]
    if len(run) == RUN_LENGTH and (
        all(x > cl for x in run) or all(x < cl for x in run)
    ):
        found.append(("XBAR", 2, xbar))
    trend = [*previous_xbars[-(TREND_LENGTH - 1) :], xbar]
    if len(trend) == TREND_LENGTH:
        pairs = list(pairwise(trend))
        if all(a < b for a, b in pairs) or all(a > b for a, b in pairs):
            found.append(("XBAR", 3, xbar))
    return found


def judgement(cpk: Decimal | None) -> str | None:
    if cpk is None:
        return None
    if cpk >= Decimal("1.33"):
        return "CAPABLE"
    return "MARGINAL" if cpk >= 1 else "INCAPABLE"


def capability(
    xbars: Sequence[Decimal],
    ranges: Sequence[Decimal],
    lsl: Decimal | None,
    usl: Decimal | None,
    n: int = 5,
) -> dict[str, Decimal | str | None]:
    """Cp·Cpk(D43). σ̂ = R̄/d2. 20 부분군 미만은 호출자가 걸러 낸다."""
    mu = mean(xbars)
    sigma = mean(ranges) / CONSTANTS[n]["d2"]
    if sigma == 0:
        return {
            "mu": q(mu),
            "sigma": q(sigma),
            "cp": None,
            "cpk": None,
            "judgement": None,
        }
    cp = (usl - lsl) / (6 * sigma) if lsl is not None and usl is not None else None
    sides = []
    if usl is not None:
        sides.append((usl - mu) / (3 * sigma))
    if lsl is not None:
        sides.append((mu - lsl) / (3 * sigma))
    cpk = min(sides)
    return {
        "mu": q(mu),
        "sigma": q(sigma),
        "cp": None if cp is None else q(cp),
        "cpk": q(cpk),
        "judgement": judgement(cpk),
    }


def histogram(
    values: Sequence[Decimal], bins: int = 10
) -> list[dict[str, Decimal | int]]:
    """개별 측정값 구간 빈도. 모든 값이 같으면 한 칸."""
    low, high = min(values), max(values)
    if low == high:
        return [{"from": low, "to": high, "count": len(values)}]
    width = (high - low) / bins
    counts = [0] * bins
    for v in values:
        counts[min(int((v - low) / width), bins - 1)] += 1
    return [
        {"from": q(low + width * i), "to": q(low + width * (i + 1)), "count": c}
        for i, c in enumerate(counts)
    ]
