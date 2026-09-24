from __future__ import annotations

from datetime import date
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
