"""AQL 샘플링 계획 — KS Q ISO 2859-1, 일반 검사 수준 II, 1회 샘플링 (DSN-14 Q2).

**표는 코드 상수다. DB에 두지 않는다**(설계 4장). 로트 크기 → 시료 문자 → 시료 수·Ac/Re.

보통 검사(Table 2-A)만 구현한다. Ac 값은 로트 크기와 AQL이 한 칸씩 움직이면 같이 한 칸씩
움직이는 사다리꼴이라, 표를 그대로 베끼지 않고 그 규칙으로 뽑는다 — 아래 `_AC` 수열의
자리를 `letter - H + AQL`로 찾는다. 자리가 수열을 벗어나면 표의 화살표와 같은 뜻이므로
위아래 첫 번째 계획으로 옮긴다.
"""

from __future__ import annotations

from decimal import Decimal

# 시료 문자와 시료 수(일반 검사 수준 II). 색인이 표의 행 번호다.
_LETTERS: tuple[tuple[str, int], ...] = (
    ("A", 2),
    ("B", 3),
    ("C", 5),
    ("D", 8),
    ("E", 13),
    ("F", 20),
    ("G", 32),
    ("H", 50),
    ("J", 80),
    ("K", 125),
    ("L", 200),
    ("M", 315),
    ("N", 500),
    ("P", 800),
    ("Q", 1250),
    ("R", 2000),
)
# 로트 크기 상한 → 시료 문자 색인. 마지막은 상한 없음.
_LOT_BANDS: tuple[tuple[int, int], ...] = (
    (8, 0),
    (15, 1),
    (25, 2),
    (50, 3),
    (90, 4),
    (150, 5),
    (280, 6),
    (500, 7),
    (1200, 8),
    (3200, 9),
    (10000, 10),
    (35000, 11),
    (150000, 12),
    (500000, 13),
)
_LAST_BAND = 14  # 500,001 이상

# 합격 판정 개수 사다리. Re는 언제나 Ac+1이다.
_AC: tuple[int, ...] = (0, 1, 2, 3, 5, 7, 10, 14, 21)
# 기준에 적을 수 있는 AQL. 표의 열 순서이며 왼쪽이 엄격하다.
AQLS: tuple[str, ...] = ("0.65", "1.0", "1.5", "2.5", "4.0", "6.5")
# 사다리의 기준점: 시료 문자 H(=50)에서 AQL 0.65면 Ac 0이다.
_ORIGIN = 7


def label(value: object) -> str:
    """DB의 numeric(5,3) AQL을 표의 열 이름으로 되돌린다 — 2.500이 아니라 "2.5"다.

    표에 없는 값이면 그대로 돌려준다. 호출 쪽이 찾지 못해 터지는 편이, 엉뚱한 열을
    고르는 것보다 낫다.
    """
    if value is None:
        return ""
    number = Decimal(str(value)).normalize()
    for aql in AQLS:
        if Decimal(aql) == number:
            return aql
    return str(number)


def letter_for(lot_size: int) -> str:
    """로트 크기의 시료 문자."""
    return _LETTERS[_band(lot_size)][0]


def _band(lot_size: int) -> int:
    if lot_size < 2:
        return 0
    for limit, index in _LOT_BANDS:
        if lot_size <= limit:
            return index
    return _LAST_BAND


def tightened(aql: str) -> str:
    """강화 검사로 볼 AQL.

    **Table 2-B(강화 검사 표)를 쓰지 않는다.** 그 표를 옮겨 적는 대신 '한 단계 엄격한
    AQL로 본다'는 규칙으로 대신한다 — 설명할 수 있고 표를 지어내지 않는다. 가장 엄격한
    AQL이면 더 조일 곳이 없어 그대로 둔다.
    """
    index = AQLS.index(aql)
    return AQLS[max(0, index - 1)]


def plan(lot_size: int, aql: str, level: str = "NORMAL") -> dict[str, object]:
    """`{letter, sampleSize, acceptNumber, rejectNumber, aql, isFullInspection}`.

    시료 수가 로트 크기 이상이면 전수 검사다(ISO 2859-1 9.3). 그때 시료 수는 로트 크기다.
    """
    if lot_size < 1:
        raise ValueError("로트 크기는 1 이상이어야 한다")
    used = tightened(aql) if level == "TIGHTENED" else aql
    column = AQLS.index(used)
    row = _band(lot_size)
    step = row - _ORIGIN + column
    if step < 0:  # 표의 ↓ — 첫 번째 아래 계획
        row, step = _ORIGIN - column, 0
    elif step >= len(_AC):  # 표의 ↑ — 첫 번째 위 계획
        row, step = _ORIGIN + len(_AC) - 1 - column, len(_AC) - 1
    letter, size = _LETTERS[row]
    full = size >= lot_size
    return {
        "letter": letter,
        "sampleSize": lot_size if full else size,
        "acceptNumber": _AC[step],
        "rejectNumber": _AC[step] + 1,
        "aql": used,
        "isFullInspection": full,
    }


def judge(defect_count: int, accept_number: int, items_passed: bool) -> str:
    """AQL 판정 — **시료 불량 개수가 Ac 이하이고 필수 항목이 모두 합격**이어야 합격(Q2).

    둘 중 하나라도 어긋나면 불합격이다. 계수(불량 개수)와 계량(항목 측정)을 함께 본다.
    """
    return "PASS" if defect_count <= accept_number and items_passed else "FAIL"


def lot_size_of(value: object) -> int:
    """로트 수량을 시료 계획에 쓸 정수로 내린다 — 2.5개를 검사할 수는 없다."""
    return int(Decimal(str(value)))
