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
Purpose = Literal["RAW", "FG"]
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


class LocationCreate(ApiModel):
    location_type: Literal["NORMAL", "QUARANTINE"] = Field(
        "NORMAL", alias="locationType"
    )
    code: str = Field(pattern=CODE)
    name: str = Field(min_length=1, max_length=100)
    is_default: bool = Field(False, alias="isDefault")


class LocationUpdate(ApiModel):
    location_type: Literal["NORMAL", "QUARANTINE"] | None = Field(
        None, alias="locationType"
    )
    name: str | None = Field(None, min_length=1, max_length=100)
    is_default: bool | None = Field(None, alias="isDefault")
    is_active: bool | None = Field(None, alias="isActive")


class ItemCreate(ApiModel):
    item_code: str = Field(alias="itemCode", pattern=ITEM_CODE)
    name: str = Field(min_length=1, max_length=100)
    base_unit: str = Field(alias="baseUnit", min_length=1, max_length=10)
    item_class: Purpose = Field(alias="itemClass")


class ItemUpdate(ApiModel):
    name: str | None = Field(None, min_length=1, max_length=100)
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
