from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SourceKind = Literal["ELECTRIC", "FUEL", "HEAT", "UTILITY"]
MeasureUnit = Literal["kWh", "Nm3", "m3", "ton"]


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class EnergySourceCreate(ApiModel):
    source_code: str = Field(alias="sourceCode", pattern=r"^[A-Z][A-Z0-9_]{1,19}$")
    name: str = Field(min_length=1, max_length=50)
    source_kind: SourceKind = Field(alias="sourceKind")
    measure_unit: MeasureUnit = Field(alias="measureUnit")
    is_billable: bool = Field(True, alias="isBillable")
    is_active: bool = Field(True, alias="isActive")


class EnergySourceUpdate(ApiModel):
    source_code: str | None = Field(
        None, alias="sourceCode", pattern=r"^[A-Z][A-Z0-9_]{1,19}$"
    )
    name: str | None = Field(None, min_length=1, max_length=50)
    source_kind: SourceKind | None = Field(None, alias="sourceKind")
    measure_unit: MeasureUnit | None = Field(None, alias="measureUnit")
    is_billable: bool | None = Field(None, alias="isBillable")
    is_active: bool | None = Field(None, alias="isActive")


class EquipmentCreate(ApiModel):
    equipment_code: str = Field(
        alias="equipmentCode", pattern=r"^[A-Z][A-Z0-9_\-]{1,29}$"
    )
    name: str = Field(min_length=1, max_length=100)
    equipment_type: str = Field(alias="equipmentType", min_length=1, max_length=40)
    location_id: int = Field(alias="locationId", gt=0)
    is_active: bool = Field(True, alias="isActive")


class EquipmentUpdate(ApiModel):
    equipment_code: str | None = Field(
        None, alias="equipmentCode", pattern=r"^[A-Z][A-Z0-9_\-]{1,29}$"
    )
    name: str | None = Field(None, min_length=1, max_length=100)
    equipment_type: str | None = Field(
        None, alias="equipmentType", min_length=1, max_length=40
    )
    location_id: int | None = Field(None, alias="locationId", gt=0)
    is_active: bool | None = Field(None, alias="isActive")


class TariffCreate(ApiModel):
    energy_source_id: int = Field(alias="energySourceId", gt=0)
    tariff_code: str = Field(alias="tariffCode", pattern=r"^[A-Z][A-Z0-9_\-]{1,29}$")
    name: str = Field(min_length=1, max_length=100)
    contract_type: str | None = Field(None, alias="contractType", max_length=50)
    basic_charge: str = Field(alias="basicCharge", pattern=r"^\d+(\.\d{1,4})?$")
    usage_rate: str = Field(alias="usageRate", pattern=r"^\d+(\.\d{1,4})?$")
    effective_from: str = Field(
        alias="effectiveFrom", pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$"
    )
    effective_to: str | None = Field(
        None, alias="effectiveTo", pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$"
    )
    tariff_kind: Literal["FLAT", "TOU"] = Field("FLAT", alias="tariffKind")
    contract_kw: str | None = Field(
        None, alias="contractKw", pattern=r"^\d+(\.\d{1,2})?$"
    )


class TariffBandIn(ApiModel):
    season: Literal["SUMMER", "SPRING_FALL", "WINTER"]
    day_kind: Literal["WEEKDAY", "SATURDAY", "HOLIDAY"] = Field(alias="dayKind")
    hour_from: int = Field(alias="hourFrom", ge=0, le=23)
    hour_to: int = Field(alias="hourTo", ge=1, le=24)
    load_band: Literal["OFF_PEAK", "MID", "PEAK"] = Field(alias="loadBand")
    rate: str = Field(pattern=r"^\d+(\.\d{1,4})?$")


class TariffBandsReplace(ApiModel):
    """구간은 통째로 바꾼다 — 한 줄씩 고치면 하루를 덮지 못하는 중간 상태가 생긴다."""

    bands: list[TariffBandIn] = Field(max_length=216)  # 3계절 × 3요일 × 24시


class TariffUpdate(ApiModel):
    energy_source_id: int | None = Field(None, alias="energySourceId", gt=0)
    tariff_code: str | None = Field(
        None, alias="tariffCode", pattern=r"^[A-Z][A-Z0-9_\-]{1,29}$"
    )
    name: str | None = Field(None, min_length=1, max_length=100)
    contract_type: str | None = Field(None, alias="contractType", max_length=50)
    basic_charge: str | None = Field(
        None, alias="basicCharge", pattern=r"^\d+(\.\d{1,4})?$"
    )
    usage_rate: str | None = Field(
        None, alias="usageRate", pattern=r"^\d+(\.\d{1,4})?$"
    )
    effective_from: str | None = Field(
        None, alias="effectiveFrom", pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$"
    )
    effective_to: str | None = Field(
        None, alias="effectiveTo", pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$"
    )
    tariff_kind: Literal["FLAT", "TOU"] | None = Field(None, alias="tariffKind")
    contract_kw: str | None = Field(
        None, alias="contractKw", pattern=r"^\d+(\.\d{1,2})?$"
    )


# ---- F-15 계측 품질 (DSN-15 F12·F14) ----
QTY = r"^\d{1,14}(\.\d{1,6})?$"  # numeric(20,6). 음수는 DB CHECK가 막는다


class ManualReadingCreate(ApiModel):
    channel_id: int = Field(alias="channelId", gt=0)
    period_start: datetime = Field(alias="periodStart")
    value: str = Field(pattern=QTY)


class CorrectionCreate(ApiModel):
    channel_id: int = Field(alias="channelId", gt=0)
    period_start: datetime = Field(alias="periodStart")
    corrected_value: str = Field(alias="correctedValue", pattern=QTY)
    method: Literal["INTERPOLATE", "PREVIOUS", "MANUAL"]
    reason: str = Field(min_length=2, max_length=300)


class UploadRow(ApiModel):
    channel_code: str = Field(alias="channelCode", min_length=1, max_length=20)
    period_start: datetime = Field(alias="periodStart")
    value: str = Field(pattern=QTY)


class ReadingUpload(ApiModel):
    """파일은 브라우저가 푼다 — 서버는 행만 받는다(multipart를 만들지 않는다)."""

    file_name: str = Field(alias="fileName", min_length=1, max_length=200)
    rows: list[UploadRow] = Field(min_length=1, max_length=5000)


class ProductionImport(ApiModel):
    month: str = Field(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")


# ---- F-18 에너지 경보 (DSN-15 F31) ----


class AlarmRuleCreate(ApiModel):
    code: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_\-]{0,29}$")
    name: str = Field(min_length=1, max_length=100)
    alarm_kind: Literal["THRESHOLD", "PEAK", "IDLE_USAGE"] = Field(alias="alarmKind")
    meter_channel_id: int | None = Field(None, alias="meterChannelId", gt=0)
    equipment_id: int | None = Field(None, alias="equipmentId", gt=0)
    threshold: str = Field(pattern=QTY)
    unit: str = Field(min_length=1, max_length=10)
    is_active: bool = Field(True, alias="isActive")


class AlarmEvaluate(ApiModel):
    month: str | None = Field(None, pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")


# ---- F-19~F-21 에너지 경영 (DSN-15 F32·F33·F35) ----


class SavingCreate(ApiModel):
    code: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_\-]{0,29}$")
    title: str = Field(min_length=1, max_length=200)
    equipment_id: int | None = Field(None, alias="equipmentId", gt=0)
    energy_source_id: int = Field(alias="energySourceId", gt=0)
    expected_saving: Decimal = Field(
        alias="expectedSaving", gt=0, max_digits=20, decimal_places=6
    )
    investment: Decimal = Field(Decimal(0), ge=0, max_digits=18, decimal_places=2)
    start_on: date = Field(alias="startOn")
    baseline_start_on: date = Field(alias="baselineStartOn")
    baseline_end_on: date = Field(alias="baselineEndOn")
    review_end_on: date | None = Field(None, alias="reviewEndOn")


class ReviewCreate(ApiModel):
    month: str = Field(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")
    issues: str | None = Field(None, max_length=1800)


class GhgCreate(ApiModel):
    year: str = Field(pattern=r"^[0-9]{4}$")


# ---- F-13 환산·배출계수 (FS-018k) ----
FACTOR = r"^\d{1,12}(\.\d{1,6})?$"  # numeric(18,6). 0은 서비스에서 거부(> 0)
YEAR = r"^[0-9]{4}$"


class FactorCreate(ApiModel):
    energy_source_id: int = Field(alias="energySourceId", gt=0)
    factor_kind: Literal["PRIMARY", "EMISSION"] = Field(alias="factorKind")
    effective_year: str = Field(alias="effectiveYear", pattern=YEAR)
    factor_value: str = Field(alias="factorValue", pattern=FACTOR)
    source_note: str = Field(alias="sourceNote", min_length=1, max_length=200)


class FactorUpdate(ApiModel):
    # 에너지원·계수 유형은 바꾸지 않는다(단위가 함께 바뀌고 탭을 넘나든다). 새로 등록한다.
    effective_year: str | None = Field(None, alias="effectiveYear", pattern=YEAR)
    factor_value: str | None = Field(None, alias="factorValue", pattern=FACTOR)
    source_note: str | None = Field(
        None, alias="sourceNote", min_length=1, max_length=200
    )


# ---- F-12 계측기·채널 (FS-018l) ----
METER_CODE = r"^[A-Z][A-Z0-9_\-]{1,39}$"
CHANNEL_CODE = r"^[A-Z][A-Z0-9_\-]{1,19}$"
ScopeKind = Literal["factory", "site_total"]
MeasurementKind = Literal["CUMULATIVE", "INSTANT"]


class MeterCreate(ApiModel):
    meter_code: str = Field(alias="meterCode", pattern=METER_CODE)
    name: str = Field(min_length=1, max_length=100)
    location_id: int = Field(alias="locationId", gt=0)
    equipment_id: int | None = Field(None, alias="equipmentId", gt=0)
    parent_meter_id: int | None = Field(None, alias="parentMeterId", gt=0)
    scope_kind: ScopeKind = Field(alias="scopeKind")


class MeterUpdate(ApiModel):
    meter_code: str | None = Field(None, alias="meterCode", pattern=METER_CODE)
    name: str | None = Field(None, min_length=1, max_length=100)
    location_id: int | None = Field(None, alias="locationId", gt=0)
    equipment_id: int | None = Field(None, alias="equipmentId", gt=0)
    parent_meter_id: int | None = Field(None, alias="parentMeterId", gt=0)
    scope_kind: ScopeKind | None = Field(None, alias="scopeKind")


class ChannelCreate(ApiModel):
    channel_code: str = Field(alias="channelCode", pattern=CHANNEL_CODE)
    name: str = Field(min_length=1, max_length=50)
    energy_source_id: int = Field(alias="energySourceId", gt=0)
    measurement_kind: MeasurementKind = Field(alias="measurementKind")
    unit: str = Field(min_length=1, max_length=10)
    multiplier: str = Field("1", pattern=FACTOR)
    is_active: bool = Field(True, alias="isActive")


class ChannelUpdate(ApiModel):
    channel_code: str | None = Field(None, alias="channelCode", pattern=CHANNEL_CODE)
    name: str | None = Field(None, min_length=1, max_length=50)
    energy_source_id: int | None = Field(None, alias="energySourceId", gt=0)
    measurement_kind: MeasurementKind | None = Field(None, alias="measurementKind")
    unit: str | None = Field(None, min_length=1, max_length=10)
    multiplier: str | None = Field(None, pattern=FACTOR)
    is_active: bool | None = Field(None, alias="isActive")


# ---- F-09 사업장·공간 (FS-018m) ----
PLACE_CODE = r"^[A-Z][A-Z0-9_\-]{1,29}$"
LocationKind = Literal["building", "zone", "workcenter"]


class SiteCreate(ApiModel):
    site_code: str = Field(alias="siteCode", pattern=PLACE_CODE)
    name: str = Field(min_length=1, max_length=100)
    timezone: str = Field("Asia/Seoul", min_length=1, max_length=60)


class SiteUpdate(ApiModel):
    site_code: str | None = Field(None, alias="siteCode", pattern=PLACE_CODE)
    name: str | None = Field(None, min_length=1, max_length=100)
    timezone: str | None = Field(None, min_length=1, max_length=60)


class LocationCreate(ApiModel):
    site_id: int = Field(alias="siteId", gt=0)
    parent_location_id: int | None = Field(None, alias="parentLocationId", gt=0)
    location_code: str = Field(alias="locationCode", pattern=PLACE_CODE)
    name: str = Field(min_length=1, max_length=100)
    kind: LocationKind


class LocationUpdate(ApiModel):
    # 사업장은 바꾸지 않는다. 계측기가 (공간, 사업장)을 함께 참조한다.
    parent_location_id: int | None = Field(None, alias="parentLocationId", gt=0)
    location_code: str | None = Field(None, alias="locationCode", pattern=PLACE_CODE)
    name: str | None = Field(None, min_length=1, max_length=100)
    kind: LocationKind | None = None


# ---- F-05 생산량 등록 (FS-018i) ----
QTY = r"^\d{1,15}(\.\d{1,3})?$"  # numeric(18,3), 0 허용
ITEM = r"^[A-Z0-9][A-Z0-9_\-]{1,39}$"


class ProductionCreate(ApiModel):
    equipment_id: int = Field(alias="equipmentId", gt=0)
    item_code: str = Field(alias="itemCode", pattern=ITEM)
    start_date: date = Field(alias="startDate")
    end_date: date = Field(
        alias="endDate"
    )  # 포함. 서버가 [시작 00:00, 종료+1 00:00)로 바꾼다
    production_qty: str = Field(alias="productionQty", pattern=QTY)
    unit: str = Field(min_length=1, max_length=10)


class ProductionUpdate(ApiModel):
    equipment_id: int | None = Field(None, alias="equipmentId", gt=0)
    item_code: str | None = Field(None, alias="itemCode", pattern=ITEM)
    start_date: date | None = Field(None, alias="startDate")
    end_date: date | None = Field(None, alias="endDate")
    production_qty: str | None = Field(None, alias="productionQty", pattern=QTY)
    unit: str | None = Field(None, min_length=1, max_length=10)
