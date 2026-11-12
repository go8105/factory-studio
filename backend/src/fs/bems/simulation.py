"""BEMS 1시간 진행 모델 (FS-025 모듈 설계 5장, D21). 결정적이고 외부 데이터가 없다.

실제 장비·날씨 연계가 없으므로 이 모델이 "명령·설정값·스케줄 → 공조 운전 → 환경·전력" 인과를 만든다.
상수는 이 파일 한 곳에만 둔다 — 시연 감각에 맞춰 조정할 수 있게(보정 여지).
시드(`backend/seed/generate.py` `_bems`)의 과거 관측도 같은 모델로 만든다.
"""

from __future__ import annotations

from decimal import Decimal

Q2 = Decimal("0.01")
Q3 = Decimal("0.001")

# 외기 대리값(℃): 시각별 고정 곡선. 최저 05시 18℃, 최고 15시 29℃.
OUTDOOR = [
    19,
    18.6,
    18.3,
    18.1,
    18.0,
    18.0,
    18.5,
    19.5,
    21,
    22.5,
    24,
    25.5,
    26.8,
    27.8,
    28.6,
    29.0,
    28.7,
    27.9,
    26.6,
    25,
    23.6,
    22.2,
    20.9,
    19.8,
]
OUTDOOR_PULL = Decimal("0.25")  # 외기 쪽으로 끌리는 비율(단열)
HVAC_TEMP_STEP = Decimal("1.2")  # 냉·난방 1시간 온도 변화 한도
HUMIDITY_COOL = Decimal("1.5")  # 냉방 제습 %p
HUMIDITY_OUTDOOR = Decimal(55)
HUMIDITY_PULL = Decimal("0.1")
CO2_FLOOR = Decimal(420)
CO2_OCCUPIED = Decimal(120)  # 사무동 재실 시간 +ppm/h
CO2_IDLE = Decimal(
    -30
)  # 비재실: 자연 환기로 감소(FS-025c 보정 — +10이면 밤새 쌓여 경보가 다시 떴다)
CO2_VENT = Decimal(150)  # 공조기 운전(환기) −ppm/h
OCCUPIED_HOURS = range(9, 18)  # 사무동 재실(평일 09~18시)
# 미세먼지(㎍/㎥): 외기 쪽으로 끌리고, 재실이면 늘고, 공조 운전(필터)이면 준다.
PM25_OUTDOOR = Decimal(28)
PM25_PULL = Decimal("0.3")
PM25_OCCUPIED = Decimal(5)
PM25_FILTER = Decimal(7)
PM25_FLOOR = Decimal(5)
# 조도(lx): 창으로 드는 자연광 + 조명 회로가 켜져 있으면 더한다. 누적이 아니라 그 시각의 값이다.
DAYLIGHT = [
    0,
    0,
    0,
    0,
    0,
    0,
    30,
    120,
    260,
    380,
    460,
    520,
    540,
    520,
    460,
    380,
    260,
    140,
    40,
    0,
    0,
    0,
    0,
    0,
]
LUX_LIGHTING = Decimal(420)
# 재실 인원(명): 구역 용도별 최대. 사무동은 점심(12시)에 절반으로 준다.
OCCUPANCY_PEAK = {
    "OFFICE": Decimal(24),
    "PRODUCTION": Decimal(12),
    "UTILITY": Decimal(1),
}
LUNCH_HOUR = 12
FAN_SHARE = Decimal("0.25")  # 송풍 전력 = 정격 × 0.25
LOAD_BASE = Decimal("0.4")  # 냉·난방 전력 = 정격 × min(1, 0.4 + 0.15 × |편차|)
LOAD_PER_DEGREE = Decimal("0.15")
# 조명·사무동 콘센트(kWh/h): 평일 08~19시 주간값, 그 외 야간값. 합 + 공조가 FEMS 수전 공용 부하(주간 25·야간 15)를 넘지 않게.
DAY_HOURS = range(8, 19)
LIGHTING = (Decimal(8), Decimal(2))
OFFICE = (Decimal(4), Decimal(3))
DEFAULT_SETPOINTS = {
    "COOL_TEMP": Decimal(26),
    "HEAT_TEMP": Decimal(20),
    "CO2_MAX": Decimal(1000),
}
SETPOINT_RANGE = {
    "COOL_TEMP": (Decimal(20), Decimal(30)),
    "HEAT_TEMP": (Decimal(16), Decimal(24)),
    "CO2_MAX": (Decimal(600), Decimal(2000)),
}
SETPOINT_BAND = Decimal(2)  # 냉방 ≥ 난방 + 2


def outdoor(hour: int) -> Decimal:
    return Decimal(str(OUTDOOR[hour]))


def start_values(hour: int) -> dict[str, str]:
    """관측 이력이 없는 센서의 시작값. 조도·재실은 누적이 아니라 매 시각 다시 계산한다."""
    return {
        "TEMP": str(outdoor(hour)),
        "HUMIDITY": "50",
        "CO2": "450",
        "PM25": str(PM25_OUTDOOR),
    }


def daytime(hour: int, weekday: bool) -> bool:
    return weekday and hour in DAY_HOURS


def next_temperature(
    current: Decimal, hour: int, state: str, setpoints: dict[str, Decimal]
) -> Decimal:
    value = current + OUTDOOR_PULL * (outdoor(hour) - current)
    if state == "COOL" and value > setpoints["COOL_TEMP"]:
        value = max(setpoints["COOL_TEMP"], value - HVAC_TEMP_STEP)
    elif state == "HEAT" and value < setpoints["HEAT_TEMP"]:
        value = min(setpoints["HEAT_TEMP"], value + HVAC_TEMP_STEP)
    return value.quantize(Q2)


def next_humidity(current: Decimal, state: str) -> Decimal:
    value = current + HUMIDITY_PULL * (HUMIDITY_OUTDOOR - current)
    if state == "COOL":
        value -= HUMIDITY_COOL
    return min(Decimal(70), max(Decimal(30), value)).quantize(Q2)


def next_co2(
    current: Decimal, hour: int, weekday: bool, office: bool, state: str
) -> Decimal:
    occupied = office and weekday and hour in OCCUPIED_HOURS
    value = current + (CO2_OCCUPIED if occupied else CO2_IDLE)
    if state != "OFF":
        value -= CO2_VENT
    return max(CO2_FLOOR, value).quantize(Q2)


def next_pm25(current: Decimal, occupied: bool, state: str) -> Decimal:
    """외기 쪽으로 끌리고, 재실이면 늘고, 공조기가 돌면 필터로 준다."""
    value = current + PM25_PULL * (PM25_OUTDOOR - current)
    if occupied:
        value += PM25_OCCUPIED
    if state != "OFF":
        value -= PM25_FILTER
    return max(PM25_FLOOR, value).quantize(Q2)


def lux(hour: int, lighting_on: bool) -> Decimal:
    """그 시각의 조도. 자연광 + 조명 회로(켜짐)."""
    value = Decimal(DAYLIGHT[hour]) + (LUX_LIGHTING if lighting_on else Decimal(0))
    return value.quantize(Q2)


def occupancy(hour: int, weekday: bool, zone_kind: str) -> Decimal:
    """그 시각의 재실 인원. 근무 시간 밖과 휴일·주말은 0명이다."""
    if not weekday or hour not in OCCUPIED_HOURS:
        return Decimal(0).quantize(Q2)
    peak = OCCUPANCY_PEAK.get(zone_kind, Decimal(0))
    if hour == LUNCH_HOUR:
        peak /= 2
    return peak.quantize(Q2)


def hvac_power(
    state: str, rated_kw: Decimal, temperature: Decimal, setpoints: dict[str, Decimal]
) -> Decimal:
    if state == "OFF":
        return Decimal("0.000")
    if state == "FAN":
        return (rated_kw * FAN_SHARE).quantize(Q3)
    target = setpoints["COOL_TEMP"] if state == "COOL" else setpoints["HEAT_TEMP"]
    load = min(Decimal(1), LOAD_BASE + LOAD_PER_DEGREE * abs(temperature - target))
    return (rated_kw * load).quantize(Q3)


def fixed_load(usage: str, hour: int, weekday: bool) -> Decimal:
    day, night = LIGHTING if usage == "LIGHTING" else OFFICE
    return (day if daytime(hour, weekday) else night).quantize(Q3)


def setpoint_error(
    kind: str, value: Decimal, current: dict[str, Decimal]
) -> str | None:
    """설정값 검증. 범위 밖·냉난방 간격 부족이면 거부 사유 코드."""
    low, high = SETPOINT_RANGE[kind]
    if not low <= value <= high:
        return "OUT_OF_RANGE"
    cool = value if kind == "COOL_TEMP" else current["COOL_TEMP"]
    heat = value if kind == "HEAT_TEMP" else current["HEAT_TEMP"]
    if cool < heat + SETPOINT_BAND:
        return "BAND_TOO_NARROW"
    return None


if __name__ == "__main__":
    sp = dict(DEFAULT_SETPOINTS)
    # 냉방 중이면 온도가 설정값 쪽으로 내려가고, 설정값을 낮추면 공조 전력이 늘어난다(AC-131).
    assert next_temperature(Decimal(28), 14, "COOL", sp) < next_temperature(
        Decimal(28), 14, "OFF", sp
    )
    lower = {**sp, "COOL_TEMP": Decimal(23)}
    assert hvac_power("COOL", Decimal(12), Decimal(26), lower) > hvac_power(
        "COOL", Decimal(12), Decimal(26), sp
    )
    assert next_co2(Decimal(900), 10, True, True, "OFF") > next_co2(
        Decimal(900), 10, True, True, "FAN"
    )
    assert setpoint_error("COOL_TEMP", Decimal(31), sp) == "OUT_OF_RANGE"
    assert setpoint_error("HEAT_TEMP", Decimal(25), sp) == "OUT_OF_RANGE"
    assert setpoint_error("COOL_TEMP", Decimal(21), sp) == "BAND_TOO_NARROW"
    # 공조기가 돌면 미세먼지가 줄고, 조명을 켜면 조도가 오르며, 휴일·야간 재실은 0명이다(DSN-16 Q4).
    assert next_pm25(Decimal(40), True, "FAN") < next_pm25(Decimal(40), True, "OFF")
    assert next_pm25(Decimal(0), False, "FAN") >= PM25_FLOOR
    assert lux(12, True) > lux(12, False) > lux(2, False)
    assert occupancy(10, True, "OFFICE") > occupancy(LUNCH_HOUR, True, "OFFICE") > 0
    assert occupancy(10, False, "OFFICE") == occupancy(3, True, "OFFICE") == 0
    print("ok")
