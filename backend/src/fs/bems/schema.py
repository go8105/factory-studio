"""BEMS 요청 본문 (FS-025 모듈 설계 8장). 수치는 문자열로 받아 Decimal로 다룬다."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CODE = r"^[A-Z][A-Z0-9-]{1,19}$"
NUMBER = r"^-?\d{1,6}(\.\d{1,2})?$"  # numeric(8,2)
Metric = Literal["TEMP", "HUMIDITY", "CO2"]
Mode = Literal["COOL", "HEAT", "FAN"]


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class ZoneCreate(ApiModel):
    code: str = Field(pattern=CODE)
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["OFFICE", "PRODUCTION", "UTILITY"]
    floor_area_m2: str | None = Field(
        None, alias="floorAreaM2", pattern=r"^\d{1,8}(\.\d{1,2})?$"
    )


class ZoneUpdate(ApiModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    floor_area_m2: str | None = Field(
        None, alias="floorAreaM2", pattern=r"^\d{1,8}(\.\d{1,2})?$"
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


class CommandCreate(ApiModel):
    zone_id: int = Field(alias="zoneId")
    hvac_unit_id: int | None = Field(None, alias="hvacUnitId")
    command: Literal["POWER_ON", "POWER_OFF", "SET_MODE", "SET_SETPOINT"]
    mode: Mode | None = None
    setpoint_kind: Literal["COOL_TEMP", "HEAT_TEMP", "CO2_MAX"] | None = Field(
        None, alias="setpointKind"
    )
    value: str | None = Field(None, pattern=NUMBER)
    note: str | None = Field(None, max_length=300)


class Slot(ApiModel):
    day_kind: Literal["WEEKDAY", "WEEKEND"] = Field(alias="dayKind")
    start_hour: int = Field(alias="startHour", ge=0, le=23)
    end_hour: int = Field(alias="endHour", ge=1, le=24)
    mode: Mode


class ScheduleReplace(ApiModel):
    slots: list[Slot] = Field(default_factory=list, max_length=24)


class Advance(ApiModel):
    hours: int = Field(1, ge=1, le=6)


class Acknowledge(ApiModel):
    note: str | None = Field(None, max_length=300)


class RuleCreate(ApiModel):
    zone_id: int = Field(alias="zoneId")
    metric: Metric
    comparator: Literal["HIGH", "LOW"]
    threshold: str = Field(pattern=NUMBER)
    duration_hours: int = Field(alias="durationHours", ge=1, le=24)
    severity: Literal["WARNING", "CRITICAL"]


class RuleUpdate(ApiModel):
    threshold: str | None = Field(None, pattern=NUMBER)
    duration_hours: int | None = Field(None, alias="durationHours", ge=1, le=24)
    severity: Literal["WARNING", "CRITICAL"] | None = None
    is_active: bool | None = Field(None, alias="isActive")
