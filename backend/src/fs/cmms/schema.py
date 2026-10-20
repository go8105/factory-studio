"""CMMS 요청 본문 (FS-029 모듈 설계 · DSN-21). 수치는 문자열로 받아 Decimal로 다룬다."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CODE = r"^[A-Z][A-Z0-9-]{1,19}$"
MONEY = r"^\d{1,16}(\.\d{1,2})?$"
AssetType = Literal[
    "INJECTION",
    "ASSEMBLY",
    "INSPECTION",
    "HVAC",
    "UTILITY",
    "OTHER",
    "MOLD",
    "LINE",
    "COMPONENT",
    "FACILITY",
]
Criticality = Literal["A", "B", "C"]
Cause = Literal["WEAR", "LUBRICATION", "ELECTRICAL", "SETTING", "EXTERNAL", "OTHER"]
CodeKind = Literal["SYMPTOM", "CAUSE", "ACTION"]
ImportSource = Literal["MES", "MES_MOLD", "BEMS"]


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class AssetCreate(ApiModel):
    code: str = Field(pattern=CODE)
    name: str = Field(min_length=1, max_length=100)
    asset_type: AssetType = Field(alias="assetType")
    location: str | None = Field(None, max_length=100)
    parent_asset_id: int | None = Field(None, alias="parentAssetId")
    manufacturer: str | None = Field(None, max_length=100)
    model: str | None = Field(None, max_length=100)
    serial_no: str | None = Field(None, alias="serialNo", max_length=60)
    installed_on: date | None = Field(None, alias="installedOn")
    acquisition_cost: str | None = Field(None, alias="acquisitionCost", pattern=MONEY)
    criticality: Criticality | None = None


class AssetUpdate(ApiModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    asset_type: AssetType | None = Field(None, alias="assetType")
    location: str | None = Field(None, max_length=100)
    parent_asset_id: int | None = Field(None, alias="parentAssetId")
    manufacturer: str | None = Field(None, max_length=100)
    model: str | None = Field(None, max_length=100)
    serial_no: str | None = Field(None, alias="serialNo", max_length=60)
    installed_on: date | None = Field(None, alias="installedOn")
    acquisition_cost: str | None = Field(None, alias="acquisitionCost", pattern=MONEY)
    criticality: Criticality | None = None
    is_active: bool | None = Field(None, alias="isActive")


class AssetImport(ApiModel):
    source: ImportSource
    source_codes: list[str] = Field(alias="sourceCodes", min_length=1, max_length=200)


class FailureCodeCreate(ApiModel):
    kind: CodeKind
    code: str = Field(pattern=CODE)
    name: str = Field(min_length=1, max_length=100)
    cause_category: Cause | None = Field(None, alias="causeCategory")


class FailureCodeUpdate(ApiModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    cause_category: Cause | None = Field(None, alias="causeCategory")
    is_active: bool | None = Field(None, alias="isActive")
