"""BEMS 요청 본문 (FS-025 모듈 설계 8장). 수치는 문자열로 받아 Decimal로 다룬다."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CODE = r"^[A-Z][A-Z0-9-]{1,19}$"
NUMBER = r"^-?\d{1,6}(\.\d{1,2})?$"  # numeric(8,2)
Metric = Literal["TEMP", "HUMIDITY", "CO2", "PM25", "LUX", "OCCUPANCY"]
# 환경 경보 규칙은 지표 3종 그대로다(DSN-16 §4-2는 센서만 6종으로 늘렸다).
AlarmMetric = Literal["TEMP", "HUMIDITY", "CO2"]
AMOUNT = r"^\d{1,8}(\.\d{1,2})?$"  # numeric(10,2) 양수
Mode = Literal["COOL", "HEAT", "FAN"]
FLOOR = r"^(B[1-9]\d?|[1-9]\d{0,2}F|RF)$"  # 지하 B1, 지상 3F, 옥상 RF


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class ZoneCreate(ApiModel):
    code: str = Field(pattern=CODE)
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["OFFICE", "PRODUCTION", "UTILITY"]
    floor_area_m2: str | None = Field(
        None, alias="floorAreaM2", pattern=r"^\d{1,8}(\.\d{1,2})?$"
    )
    building_id: int | None = Field(None, alias="buildingId")
    floor_label: str | None = Field(None, alias="floorLabel", pattern=FLOOR)
    department_code: str | None = Field(
        None, alias="departmentCode", min_length=1, max_length=30
    )


class ZoneUpdate(ApiModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    floor_area_m2: str | None = Field(
        None, alias="floorAreaM2", pattern=r"^\d{1,8}(\.\d{1,2})?$"
    )
    is_active: bool | None = Field(None, alias="isActive")
    building_id: int | None = Field(None, alias="buildingId")
    floor_label: str | None = Field(None, alias="floorLabel", pattern=FLOOR)
    department_code: str | None = Field(
        None, alias="departmentCode", min_length=1, max_length=30
    )


class BuildingCreate(ApiModel):
    code: str = Field(pattern=CODE)
    name: str = Field(min_length=1, max_length=100)
    floors: int = Field(ge=1, le=200)
    gross_area_m2: str = Field(alias="grossAreaM2", pattern=r"^\d{1,10}(\.\d{1,2})?$")


class BuildingUpdate(ApiModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    floors: int | None = Field(None, ge=1, le=200)
    gross_area_m2: str | None = Field(
        None, alias="grossAreaM2", pattern=r"^\d{1,10}(\.\d{1,2})?$"
    )
    is_active: bool | None = Field(None, alias="isActive")


class MeterCreate(ApiModel):
    zone_id: int = Field(alias="zoneId")
    code: str = Field(pattern=CODE)
    name: str = Field(min_length=1, max_length=100)
    usage: Literal["LIGHTING", "HVAC", "OFFICE", "OTHER"]


class SensorCreate(ApiModel):
    zone_id: int = Field(alias="zoneId")
    code: str = Field(pattern=CODE)
    metric: Metric


class NameUpdate(ApiModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    is_active: bool | None = Field(None, alias="isActive")


class ActiveUpdate(ApiModel):
    is_active: bool | None = Field(None, alias="isActive")


class HvacCreate(ApiModel):
    zone_id: int = Field(alias="zoneId")
    code: str = Field(pattern=CODE)
    name: str = Field(min_length=1, max_length=100)
    meter_id: int | None = Field(None, alias="meterId")
    rated_kw: str = Field(alias="ratedKw", pattern=r"^\d{1,6}(\.\d{1,2})?$")


class HvacUpdate(ApiModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    meter_id: int | None = Field(None, alias="meterId")
    rated_kw: str | None = Field(
        None, alias="ratedKw", pattern=r"^\d{1,6}(\.\d{1,2})?$"
    )
    is_active: bool | None = Field(None, alias="isActive")


class LightingCreate(ApiModel):
    zone_id: int = Field(alias="zoneId")
    code: str = Field(pattern=CODE)
    name: str = Field(min_length=1, max_length=100)
    meter_id: int | None = Field(None, alias="meterId")
    rated_kw: str = Field(alias="ratedKw", pattern=r"^\d{1,8}(\.\d{1,2})?$")


class LightingUpdate(ApiModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    meter_id: int | None = Field(None, alias="meterId")
    rated_kw: str | None = Field(
        None, alias="ratedKw", pattern=r"^\d{1,8}(\.\d{1,2})?$"
    )
    is_active: bool | None = Field(None, alias="isActive")


class CommandCreate(ApiModel):
    zone_id: int = Field(alias="zoneId")
    hvac_unit_id: int | None = Field(None, alias="hvacUnitId")
    lighting_circuit_id: int | None = Field(None, alias="lightingCircuitId")
    command: Literal["POWER_ON", "POWER_OFF", "SET_MODE", "SET_SETPOINT"]
    mode: Mode | None = None
    setpoint_kind: Literal["COOL_TEMP", "HEAT_TEMP", "CO2_MAX"] | None = Field(
        None, alias="setpointKind"
    )
    value: str | None = Field(None, pattern=NUMBER)
    note: str | None = Field(None, max_length=300)


class Slot(ApiModel):
    day_kind: Literal["WEEKDAY", "WEEKEND", "HOLIDAY"] = Field(alias="dayKind")
    start_hour: int = Field(alias="startHour", ge=0, le=23)
    end_hour: int = Field(alias="endHour", ge=1, le=24)
    mode: (
        Mode | Literal["ON"]
    )  # 공조기는 COOL·HEAT·FAN, 조명 회로는 ON (서비스가 대상별로 확인)


class ScheduleReplace(ApiModel):
    slots: list[Slot] = Field(default_factory=list, max_length=24)


class Advance(ApiModel):
    hours: int = Field(1, ge=1, le=6)


class Acknowledge(ApiModel):
    note: str | None = Field(None, max_length=300)


class ComfortCreate(ApiModel):
    zone_kind: Literal["OFFICE", "PRODUCTION", "UTILITY"] = Field(alias="zoneKind")
    metric: Metric
    low: str | None = Field(None, pattern=AMOUNT)
    high: str | None = Field(None, pattern=AMOUNT)
    occupied_only: bool = Field(True, alias="occupiedOnly")


class ComfortUpdate(ApiModel):
    low: str | None = Field(None, pattern=AMOUNT)
    high: str | None = Field(None, pattern=AMOUNT)
    occupied_only: bool | None = Field(None, alias="occupiedOnly")


class EquipmentRuleCreate(ApiModel):
    code: str = Field(pattern=CODE)
    condition: Literal["COMMAND_REJECTED", "LONG_RUN"]
    hvac_unit_id: int | None = Field(None, alias="hvacUnitId")
    threshold: str = Field(pattern=AMOUNT)
    severity: Literal["WARNING", "CRITICAL"]


class EquipmentRuleUpdate(ApiModel):
    hvac_unit_id: int | None = Field(None, alias="hvacUnitId")
    threshold: str | None = Field(None, pattern=AMOUNT)
    severity: Literal["WARNING", "CRITICAL"] | None = None
    is_active: bool | None = Field(None, alias="isActive")


class RuleCreate(ApiModel):
    zone_id: int = Field(alias="zoneId")
    metric: AlarmMetric
    comparator: Literal["HIGH", "LOW"]
    threshold: str = Field(pattern=NUMBER)
    duration_hours: int = Field(alias="durationHours", ge=1, le=24)
    severity: Literal["WARNING", "CRITICAL"]


class RuleUpdate(ApiModel):
    threshold: str | None = Field(None, pattern=NUMBER)
    duration_hours: int | None = Field(None, alias="durationHours", ge=1, le=24)
    severity: Literal["WARNING", "CRITICAL"] | None = None
    is_active: bool | None = Field(None, alias="isActive")
