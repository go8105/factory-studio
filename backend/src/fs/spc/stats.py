"""SPC 계산 (FS-028 모듈 설계 5장 · DSN-17 Q1·Q3). 부동소수 오차로 한계 경계 판정이 흔들리지 않게 Decimal만 쓴다.

부분군 크기는 1~10이다. n=1은 I-MR로, 이웃 차이(MR)를 R 자리에 넣고 상수표의 n=1 줄
(E2 2.660을 A2 자리에, MR의 D3·D4·d2)을 쓴다. 그래서 한계·공정능력 식은 X̄-R과 같은 코드를 탄다.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal
from itertools import pairwise


def _k(a2: str, d3: str, d4: str, d2: str) -> dict[str, Decimal]:
    return {
        "A2": Decimal(a2),
        "D3": Decimal(d3),
        "D4": Decimal(d4),
        "d2": Decimal(d2),
    }


# n=1은 I-MR: A2 자리가 E2(2.660)이고 D3·D4·d2는 이웃 차이(MR, n=2)의 값이다.
CONSTANTS = {
    1: _k("2.660", "0", "3.267", "1.128"),
    2: _k("1.880", "0", "3.267", "1.128"),
    3: _k("1.023", "0", "2.574", "1.693"),
    4: _k("0.729", "0", "2.282", "2.059"),
    5: _k("0.577", "0", "2.114", "2.326"),
    6: _k("0.483", "0", "2.004", "2.534"),
    7: _k("0.419", "0.076", "1.924", "2.704"),
    8: _k("0.373", "0.136", "1.864", "2.847"),
    9: _k("0.337", "0.184", "1.816", "2.970"),
    10: _k("0.308", "0.223", "1.777", "3.078"),
}
CHARTS = {"XBAR_R": ("XBAR", "R"), "I_MR": ("I", "MR")}
DEFAULT_RULES = frozenset({1, 2, 3})  # 특성별 선택이 없으면 이것(FS-028 D41)
MIN_BASIS = 20  # 한계 게시·공정능력 최소 유효 부분군(D40, 13장 5)
RUN_LENGTH = 9  # 규칙 2: 중심선 한쪽 연속 9점
TREND_LENGTH = 6  # 규칙 3: 연속 6점 증가 또는 감소
ALTERNATE_LENGTH = 14  # 규칙 4: 위아래 번갈아 14점
HUG_LENGTH = 15  # 규칙 7: 1σ 안 연속 15점
AWAY_LENGTH = 8  # 규칙 8: 1σ 밖 연속 8점
_Q = Decimal("0.000001")


def q(value: Decimal) -> Decimal:
    """numeric(14,6) 저장 전 반올림(ROUND_HALF_UP)."""
    return value.quantize(_Q, rounding=ROUND_HALF_UP)


def mean(values: Sequence[Decimal]) -> Decimal:
    return sum(values, Decimal(0)) / len(values)


def subgroup(
    values: Sequence[Decimal], previous: Decimal | None = None
) -> tuple[Decimal, Decimal]:
    """(X̄, R). n=1이면 (개별값, 이웃 차이 MR) — 첫 점은 앞이 없어 MR 0으로 둔다."""
    if len(values) == 1:
        only = values[0]
        return q(only), q(abs(only - previous) if previous is not None else Decimal(0))
    return q(mean(values)), q(max(values) - min(values))


def _ranges(ranges: Sequence[Decimal], n: int) -> Sequence[Decimal]:
    """I-MR의 첫 점 MR은 진짜 이웃 차이가 아니다(0으로 채운 값). 평균에서 뺀다."""
    return ranges[1:] if n == 1 and len(ranges) > 1 else ranges


def limits(
    xbars: Sequence[Decimal], ranges: Sequence[Decimal], n: int = 5
) -> dict[str, Decimal]:
    k = CONSTANTS[n]
    x_cl, r_cl = mean(xbars), mean(_ranges(ranges, n))
    return {
        "xbar_cl": q(x_cl),
        "xbar_ucl": q(x_cl + k["A2"] * r_cl),
        "xbar_lcl": q(x_cl - k["A2"] * r_cl),
        "r_cl": q(r_cl),
        "r_ucl": q(k["D4"] * r_cl),
        "r_lcl": q(k["D3"] * r_cl),
    }


def _zone(
    values: Sequence[Decimal], cl: Decimal, sigma: Decimal
) -> list[tuple[int, int]]:
    """점마다 (중심선 기준 쪽, σ 구역). 쪽은 +1·-1·0(중심선과 같음), 구역은 1σ 안이면 0, 넘은 만큼 1~3."""
    out = []
    for value in values:
        d = value - cl
        step = abs(d) / sigma if sigma > 0 else Decimal(0)
        level = 3 if step > 3 else 2 if step > 2 else 1 if step > 1 else 0
        out.append(((d > 0) - (d < 0), level))
    return out


def _nelson(points: Sequence[Decimal], cl: Decimal, sigma: Decimal) -> set[int]:
    """마지막 점에서 끝나는 규칙 2~8. points는 오래된 → 최근이고 마지막이 판정 대상이다."""
    hit: set[int] = set()
    zones = _zone(points, cl, sigma)

    def tail(length: int) -> list[tuple[int, int]] | None:
        return zones[-length:] if len(zones) >= length else None

    run = tail(RUN_LENGTH)
    if run and all(side == run[0][0] != 0 for side, _ in run):
        hit.add(2)
    if len(points) >= TREND_LENGTH:
        pairs = list(pairwise(points[-TREND_LENGTH:]))
        if all(a < b for a, b in pairs) or all(a > b for a, b in pairs):
            hit.add(3)
    if len(points) >= ALTERNATE_LENGTH:
        steps = [b - a for a, b in pairwise(points[-ALTERNATE_LENGTH:])]
        if all(step != 0 for step in steps) and all(
            (a > 0) != (b > 0) for a, b in pairwise(steps)
        ):
            hit.add(4)
    # 규칙 5·6: 마지막 점을 포함한 창에서 같은 쪽으로 구역 밖 점이 몇 개인지. 마지막 점 자신이 밖이어야 한다.
    side, level = zones[-1]
    for rule, window, need, beyond in ((5, 3, 2, 2), (6, 5, 4, 1)):
        recent = tail(window)
        if recent is None or level < beyond or side == 0:
            continue
        if sum(1 for s, lv in recent if s == side and lv >= beyond) >= need:
            hit.add(rule)
    hug = tail(HUG_LENGTH)
    if hug and all(lv == 0 for _, lv in hug):
        hit.add(7)
    away = tail(AWAY_LENGTH)
    if away and all(lv >= 1 for _, lv in away):
        hit.add(8)
    return hit


def signals(
    previous_xbars: Sequence[Decimal],
    xbar: Decimal,
    r: Decimal,
    limit: dict[str, Decimal],
    rules: frozenset[int] | set[int] = DEFAULT_RULES,
    chart_type: str = "XBAR_R",
) -> list[tuple[str, int, Decimal]]:
    """Nelson 1~8 중 쓰기로 한 규칙만 판정. previous_xbars는 같은 한계 버전의 이전 유효 부분군(오래된 → 최근).

    연속 판정은 버전마다 새로 센다(13장 3) — 호출자가 같은 버전 부분군만 넘긴다.
    조건이 이어지는 동안 점마다 이상을 기록한다(관리도 표기와 같다).
    규칙 2~8은 위치 관리도(X̄·I)에만 쓴다 — 산포 관리도(R·MR)는 규칙 1뿐이다.
    """
    position, spread = CHARTS[chart_type]
    found: list[tuple[str, int, Decimal]] = []
    if 1 in rules:
        if xbar > limit["xbar_ucl"] or xbar < limit["xbar_lcl"]:
            found.append((position, 1, xbar))
        if r > limit["r_ucl"] or r < limit["r_lcl"]:
            found.append((spread, 1, r))
    extra = rules - {1}
    if extra:
        cl = limit["xbar_cl"]
        sigma = (limit["xbar_ucl"] - cl) / 3
        points = [*previous_xbars, xbar]
        for rule in sorted(_nelson(points, cl, sigma) & extra):
            found.append((position, rule, xbar))
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
    sigma = mean(_ranges(ranges, n)) / CONSTANTS[n]["d2"]
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
