"""WMS 요청 본문 (FS-024 모듈 설계 8장). 수량은 문자열로 받아 Decimal로 다룬다."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CODE = r"^[A-Z][A-Z0-9-]{1,19}$"
ITEM_CODE = r"^[A-Z][A-Z0-9_\-]{1,39}$"
QTY = r"^\d{1,15}(\.\d{1,3})?$"  # numeric(18,3), 0은 서비스에서 거부
SIGNED_QTY = r"^-?\d{1,15}(\.\d{1,3})?$"
FACTOR = r"^\d{1,12}(\.\d{1,6})?$"  # numeric(18,6)
WarehousePurpose = Literal[
    "RAW", "SEMI", "FG", "MERCH", "LINE", "SUBCON", "DEFECT", "RETURN"
]
ItemClass = Literal["RAW", "SEMI", "FG", "MERCH", "SUPPLY"]
Purpose = WarehousePurpose | ItemClass
ManualType = Literal["OPENING", "ADJUSTMENT", "TRANSFER"]
Reason = Literal["RETURN", "SCRAP", "COUNT", "OTHER"]
SourceKind = Literal["MES_RECEIPT", "MES_ISSUE", "ERP_SHIPMENT", "ERP_PURCHASE"]


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class WarehouseCreate(ApiModel):
    code: str = Field(pattern=CODE)
    name: str = Field(min_length=1, max_length=100)
    purpose: Purpose
    is_active: bool = Field(True, alias="isActive")


class WarehouseUpdate(ApiModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    is_active: bool | None = Field(None, alias="isActive")


LocationType = Literal[
    "NORMAL", "QUARANTINE", "LINE", "RECEIVING", "SHIPPING", "RETURN"
]


class LocationCreate(ApiModel):
    location_type: LocationType = Field("NORMAL", alias="locationType")
    code: str = Field(pattern=CODE)
    name: str = Field(min_length=1, max_length=100)
    is_default: bool = Field(False, alias="isDefault")
    # 적치 추천(F14)과 위치 점유(F55)가 쓰는 칸이다. 용량이 없으면 제한 없음으로 본다.
    capacity_qty: str | None = Field(None, alias="capacityQty", pattern=QTY)
    mix_items: bool = Field(True, alias="mixItems")
    mix_lots: bool = Field(True, alias="mixLots")


class LocationUpdate(ApiModel):
    location_type: LocationType | None = Field(None, alias="locationType")
    name: str | None = Field(None, min_length=1, max_length=100)
    is_default: bool | None = Field(None, alias="isDefault")
    is_active: bool | None = Field(None, alias="isActive")
    capacity_qty: str | None = Field(None, alias="capacityQty", pattern=QTY)
    mix_items: bool | None = Field(None, alias="mixItems")
    mix_lots: bool | None = Field(None, alias="mixLots")


class ItemCreate(ApiModel):
    item_code: str = Field(alias="itemCode", pattern=ITEM_CODE)
    name: str = Field(min_length=1, max_length=100)
    base_unit: str = Field(alias="baseUnit", min_length=1, max_length=10)
    item_class: ItemClass = Field(alias="itemClass")
    lot_tracked: bool = Field(False, alias="lotTracked")
    shelf_life_days: int | None = Field(None, alias="shelfLifeDays", ge=1)
    storage_condition: str | None = Field(None, alias="storageCondition", max_length=60)
    safety_stock: str | None = Field(None, alias="safetyStock", pattern=QTY)
    max_stock: str | None = Field(None, alias="maxStock", pattern=QTY)
    abc_class: Literal["A", "B", "C"] | None = Field(None, alias="abcClass")
    plm_part_no: str | None = Field(None, alias="plmPartNo", max_length=40)
    plm_revision: str | None = Field(None, alias="plmRevision", max_length=10)


class ItemUpdate(ApiModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    base_unit: str | None = Field(None, alias="baseUnit", min_length=1, max_length=10)
    item_class: ItemClass | None = Field(None, alias="itemClass")
    lot_tracked: bool | None = Field(None, alias="lotTracked")
    shelf_life_days: int | None = Field(None, alias="shelfLifeDays", ge=1)
    storage_condition: str | None = Field(None, alias="storageCondition", max_length=60)
    safety_stock: str | None = Field(None, alias="safetyStock", pattern=QTY)
    max_stock: str | None = Field(None, alias="maxStock", pattern=QTY)
    abc_class: Literal["A", "B", "C"] | None = Field(None, alias="abcClass")
    plm_part_no: str | None = Field(None, alias="plmPartNo", max_length=40)
    plm_revision: str | None = Field(None, alias="plmRevision", max_length=10)
    is_active: bool | None = Field(None, alias="isActive")


class ItemImport(ApiModel):
    item_codes: list[str] = Field(alias="itemCodes", min_length=1, max_length=100)


class ConversionCreate(ApiModel):
    from_unit: str = Field(alias="fromUnit", min_length=1, max_length=10)
    factor: str = Field(pattern=FACTOR)


class DocumentLine(ApiModel):
    item_id: int = Field(alias="itemId")
    location_id: int | None = Field(None, alias="locationId")
    lot_no: str | None = Field(None, alias="lotNo", min_length=1, max_length=50)
    qty: str = Field(pattern=SIGNED_QTY)
    # 이동(TRANSFER) 줄만: 보낼 위치 → 받을 위치
    from_location_id: int | None = Field(None, alias="fromLocationId")
    to_location_id: int | None = Field(None, alias="toLocationId")


class DocumentCreate(ApiModel):
    document_type: ManualType = Field(alias="documentType")
    document_on: date | None = Field(None, alias="documentOn")
    reason_code: Reason | None = Field(None, alias="reasonCode")
    note: str | None = Field(None, max_length=300)
    lines: list[DocumentLine] = Field(default_factory=list, max_length=100)


class DocumentUpdate(ApiModel):
    document_on: date | None = Field(None, alias="documentOn")
    reason_code: Reason | None = Field(None, alias="reasonCode")
    note: str | None = Field(None, max_length=300)
    lines: list[DocumentLine] | None = Field(None, max_length=100)


class SourceSync(ApiModel):
    kind: SourceKind
    source_keys: list[str] = Field(alias="sourceKeys", min_length=1, max_length=200)


LotOrigin = Literal["RECEIPT", "MES", "RETURN", "OPENING"]
LotStatus = Literal["AVAILABLE", "HOLD", "EXPIRED"]


class LotCreate(ApiModel):
    item_id: int = Field(alias="itemId", gt=0)
    lot_no: str = Field(alias="lotNo", min_length=1, max_length=50)
    origin: LotOrigin = Field("RECEIPT")
    received_on: date = Field(alias="receivedOn")
    expiry_date: date | None = Field(None, alias="expiryDate")
    supplier_lot_no: str | None = Field(None, alias="supplierLotNo", max_length=50)
    status: LotStatus = Field("AVAILABLE")


class LotUpdate(ApiModel):
    expiry_date: date | None = Field(None, alias="expiryDate")
    supplier_lot_no: str | None = Field(None, alias="supplierLotNo", max_length=50)
    status: LotStatus | None = None


HoldSource = Literal["MANUAL", "QMS", "EXPIRY"]


class LotHoldCreate(ApiModel):
    source: HoldSource = "MANUAL"
    source_ref: str | None = Field(None, alias="sourceRef", max_length=60)
    reason: str = Field(min_length=2, max_length=300)
