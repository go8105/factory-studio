from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CODE = r"^[A-Z][A-Z0-9_\-]{1,29}$"
ITEM_CODE = r"^[A-Z][A-Z0-9_\-]{1,39}$"
FACTOR = r"^\d{1,12}(\.\d{1,6})?$"  # numeric(18,6). 0은 서비스에서 거부
LocationKind = Literal["building", "zone", "workcenter"]
BaseUnit = Literal["EA", "BOX", "KG", "M", "L", "SET"]
ItemType = Literal["finished", "semi_finished", "raw", "auxiliary"]


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class SiteCreate(ApiModel):
    site_code: str = Field(alias="siteCode", pattern=CODE)
    name: str = Field(min_length=1, max_length=100)
    timezone: str = Field("Asia/Seoul", min_length=1, max_length=60)


class SiteUpdate(ApiModel):
    site_code: str | None = Field(None, alias="siteCode", pattern=CODE)
    name: str | None = Field(None, min_length=1, max_length=100)
    timezone: str | None = Field(None, min_length=1, max_length=60)


class LocationCreate(ApiModel):
    site_id: int = Field(alias="siteId", gt=0)
    parent_location_id: int | None = Field(None, alias="parentLocationId", gt=0)
    location_code: str = Field(alias="locationCode", pattern=CODE)
    name: str = Field(min_length=1, max_length=100)
    kind: LocationKind


class LocationUpdate(ApiModel):
    # 사업장은 바꾸지 않는다. 상위 공간 복합 FK가 사업장을 함께 참조한다.
    parent_location_id: int | None = Field(None, alias="parentLocationId", gt=0)
    location_code: str | None = Field(None, alias="locationCode", pattern=CODE)
    name: str | None = Field(None, min_length=1, max_length=100)
    kind: LocationKind | None = None


class EquipmentCreate(ApiModel):
    location_id: int = Field(alias="locationId", gt=0)
    equipment_code: str = Field(alias="equipmentCode", pattern=CODE)
    name: str = Field(min_length=1, max_length=100)
    equipment_type: str = Field(alias="equipmentType", min_length=1, max_length=40)
    is_active: bool = Field(True, alias="isActive")


class EquipmentUpdate(ApiModel):
    location_id: int | None = Field(None, alias="locationId", gt=0)
    equipment_code: str | None = Field(None, alias="equipmentCode", pattern=CODE)
    name: str | None = Field(None, min_length=1, max_length=100)
    equipment_type: str | None = Field(
        None, alias="equipmentType", min_length=1, max_length=40
    )
    is_active: bool | None = Field(None, alias="isActive")


class ItemCreate(ApiModel):
    item_code: str = Field(alias="itemCode", pattern=ITEM_CODE)
    name: str = Field(min_length=1, max_length=100)
    base_unit: BaseUnit = Field("EA", alias="baseUnit")
    item_type: ItemType = Field("finished", alias="itemType")
    is_active: bool = Field(True, alias="isActive")


class ItemUpdate(ApiModel):
    item_code: str | None = Field(None, alias="itemCode", pattern=ITEM_CODE)
    name: str | None = Field(None, min_length=1, max_length=100)
    base_unit: BaseUnit | None = Field(None, alias="baseUnit")
    item_type: ItemType | None = Field(None, alias="itemType")
    is_active: bool | None = Field(None, alias="isActive")


class ConversionCreate(ApiModel):
    from_unit: str = Field(alias="fromUnit", min_length=1, max_length=10)
    factor: str = Field(pattern=FACTOR)


class ConversionUpdate(ApiModel):
    from_unit: str | None = Field(None, alias="fromUnit", min_length=1, max_length=10)
    factor: str | None = Field(None, pattern=FACTOR)


class ProcessCreate(ApiModel):
    process_code: str = Field(alias="processCode", pattern=CODE)
    name: str = Field(min_length=1, max_length=100)
    process_type: str = Field(alias="processType", min_length=1, max_length=20)
    is_active: bool = Field(True, alias="isActive")
    equipment_ids: list[int] = Field(default_factory=list, alias="equipmentIds")


class ProcessUpdate(ApiModel):
    process_code: str | None = Field(None, alias="processCode", pattern=CODE)
    name: str | None = Field(None, min_length=1, max_length=100)
    process_type: str | None = Field(
        None, alias="processType", min_length=1, max_length=20
    )
    is_active: bool | None = Field(None, alias="isActive")
    equipment_ids: list[int] | None = Field(None, alias="equipmentIds")


# ---- M-14 공정 경로 · M-15 BOM ----
QTY = r"^\d{1,15}(\.\d{1,3})?$"  # numeric(18,3)
RATE = r"^\d{1,3}(\.\d{1,2})?$"  # numeric(5,2), 100 미만은 서비스에서


class RouteCreate(ApiModel):
    item_id: int = Field(alias="itemId", gt=0)
    route_code: str = Field(alias="routeCode", pattern=ITEM_CODE)


class BomCreate(ApiModel):
    item_id: int = Field(alias="itemId", gt=0)
    bom_code: str = Field(alias="bomCode", pattern=ITEM_CODE)


class BomRevise(ApiModel):
    bom_code: str = Field(alias="bomCode", pattern=ITEM_CODE)


class RouteSteps(ApiModel):
    process_ids: list[int] = Field(alias="processIds", max_length=50)


class BomLineIn(ApiModel):
    material_item_id: int = Field(alias="materialItemId", gt=0)
    qty_per_unit: str = Field(alias="qtyPerUnit", pattern=QTY)
    unit: str = Field(min_length=1, max_length=10)
    loss_rate: str = Field("0", alias="lossRate", pattern=RATE)


class BomLines(ApiModel):
    lines: list[BomLineIn] = Field(max_length=100)
