from __future__ import annotations

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
