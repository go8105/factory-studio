"""QMS 요청 본문 (FS-023 모듈 설계 8장). 수치는 문자열로 받아 Decimal로 다룬다."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DEFECT_CODE = r"^[A-Z][A-Z0-9_]{1,29}$"
ITEM_CODE = r"^[A-Z][A-Z0-9_\-]{1,39}$"
NUMBER = r"^-?\d{1,11}(\.\d{1,4})?$"  # numeric(15,4)
QTY = r"^\d{1,12}(\.\d{1,3})?$"  # numeric(15,3). 0은 서비스에서 거부
Method = Literal["RANGE", "PASS_FAIL"]
Disposition = Literal["REINSPECTED", "CONCESSION", "SCRAP"]


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class DefectTypeCreate(ApiModel):
    code: str = Field(pattern=DEFECT_CODE)
    name: str = Field(min_length=1, max_length=100)
    is_active: bool = Field(True, alias="isActive")


class DefectTypeUpdate(ApiModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    is_active: bool | None = Field(None, alias="isActive")


class SpecItemIn(ApiModel):
    name: str = Field(min_length=1, max_length=100)
    method: Method
    lower_limit: str | None = Field(None, alias="lowerLimit", pattern=NUMBER)
    upper_limit: str | None = Field(None, alias="upperLimit", pattern=NUMBER)
    unit: str | None = Field(None, min_length=1, max_length=10)
    is_required: bool = Field(True, alias="isRequired")


class SpecCreate(ApiModel):
    item_code: str = Field(alias="itemCode", pattern=ITEM_CODE)
    item_name: str = Field(alias="itemName", min_length=1, max_length=100)
    note: str | None = Field(None, max_length=300)
    items: list[SpecItemIn] = Field(default_factory=list, max_length=50)


class SpecUpdate(ApiModel):
    note: str | None = Field(None, max_length=300)
    items: list[SpecItemIn] | None = Field(None, max_length=50)


class InspectionCreate(ApiModel):
    source: Literal["MES", "MANUAL"]
    lot_no: str = Field(alias="lotNo", min_length=1, max_length=50)
    sample_qty: str = Field(alias="sampleQty", pattern=QTY)
    inspected_on: date | None = Field(None, alias="inspectedOn")
    # MANUAL(MES를 끈 공간)에서만 쓴다. MES면 조회한 스냅샷을 쓴다.
    item_code: str | None = Field(None, alias="itemCode", pattern=ITEM_CODE)
    item_name: str | None = Field(None, alias="itemName", min_length=1, max_length=100)
    lot_qty: str | None = Field(None, alias="lotQty", pattern=QTY)
    unit: str | None = Field(None, min_length=1, max_length=10)
    note: str | None = Field(None, max_length=300)


class ValueIn(ApiModel):
    spec_item_id: int = Field(alias="specItemId", gt=0)
    measured_value: str | None = Field(None, alias="measuredValue", pattern=NUMBER)
    pass_value: bool | None = Field(None, alias="passValue")
    defect_type_id: int | None = Field(None, alias="defectTypeId", gt=0)


class InspectionUpdate(ApiModel):
    sample_qty: str | None = Field(None, alias="sampleQty", pattern=QTY)
    inspected_on: date | None = Field(None, alias="inspectedOn")
    note: str | None = Field(None, max_length=300)
    values: list[ValueIn] | None = Field(None, max_length=50)


class HoldRelease(ApiModel):
    disposition: Disposition
    release_inspection_id: int | None = Field(None, alias="releaseInspectionId", gt=0)
    reason: str | None = Field(None, max_length=300)
