"""CMMS 요청 본문 (FS-029 모듈 설계 · DSN-21). 수치는 문자열로 받아 Decimal로 다룬다."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CODE = r"^[A-Z][A-Z0-9-]{1,19}$"
MONEY = r"^\d{1,16}(\.\d{1,2})?$"
NUMBER = r"^-?\d{1,11}(\.\d{1,4})?$"
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


Skill = Literal["MECHANICAL", "ELECTRICAL", "UTILITY", "GENERAL"]
SignalSource = Literal["BEMS_ALARM", "SPC_SIGNAL"]


class TechnicianCreate(ApiModel):
    code: str = Field(pattern=CODE)
    name: str = Field(min_length=1, max_length=100)
    skill: Skill
    hourly_rate: str = Field(alias="hourlyRate", pattern=MONEY)
    hr_employee_code: str | None = Field(None, alias="hrEmployeeCode", max_length=30)


class TechnicianUpdate(ApiModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    skill: Skill | None = None
    hourly_rate: str | None = Field(None, alias="hourlyRate", pattern=MONEY)
    hr_employee_code: str | None = Field(None, alias="hrEmployeeCode", max_length=30)
    is_active: bool | None = Field(None, alias="isActive")


class VendorCreate(ApiModel):
    code: str = Field(pattern=CODE)
    name: str = Field(min_length=1, max_length=200)
    erp_partner_code: str | None = Field(None, alias="erpPartnerCode", max_length=40)
    phone: str | None = Field(None, max_length=30)


class VendorUpdate(ApiModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    erp_partner_code: str | None = Field(None, alias="erpPartnerCode", max_length=40)
    phone: str | None = Field(None, max_length=30)
    is_active: bool | None = Field(None, alias="isActive")


class WorkOrderCreate(ApiModel):
    asset_id: int = Field(alias="assetId")
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(None, max_length=1000)
    failure_at: datetime | None = Field(None, alias="failureAt")
    technician_id: int | None = Field(None, alias="technicianId")
    symptom_code_id: int | None = Field(None, alias="symptomCodeId")


class WorkOrderStart(ApiModel):
    technician_id: int | None = Field(None, alias="technicianId")


class WorkLogCreate(ApiModel):
    minutes: int = Field(ge=1, le=1440)
    # 한 일은 필수다 — 시간만 남으면 나중에 무엇을 했는지 알 수 없다.
    note: str = Field(min_length=1, max_length=300)
    technician_id: int | None = Field(None, alias="technicianId")


class WorkOrderComplete(ApiModel):
    cause_category: Cause = Field(alias="causeCategory")
    action: str = Field(min_length=2, max_length=500)
    action_code_id: int | None = Field(None, alias="actionCodeId")
    restored_at: datetime | None = Field(None, alias="restoredAt")
    vendor_id: int | None = Field(None, alias="vendorId")
    external_cost: str | None = Field(None, alias="externalCost", pattern=MONEY)


class CancelBody(ApiModel):
    reason: str = Field(min_length=2, max_length=300)


class SignalConvert(ApiModel):
    source: SignalSource
    source_ref: str = Field(alias="sourceRef", min_length=1, max_length=60)
    summary: str = Field(min_length=1, max_length=300)
    asset_id: int = Field(alias="assetId")
    title: str | None = Field(None, max_length=200)
    detected_at: datetime | None = Field(None, alias="detectedAt")


QTY = r"^\d{1,9}(\.\d{1,3})?$"
TriggerKind = Literal["CALENDAR", "RUN_HOURS", "SHOTS"]
CheckMethod = Literal["OK_NG", "RANGE"]


class PmPlanCreate(ApiModel):
    asset_id: int = Field(alias="assetId")
    code: str = Field(pattern=CODE)
    title: str = Field(min_length=1, max_length=200)
    checklist: str | None = Field(None, max_length=1000)
    trigger_kind: TriggerKind = Field("CALENDAR", alias="triggerKind")
    interval_days: int | None = Field(None, alias="intervalDays", ge=1, le=365)
    interval_usage: str | None = Field(None, alias="intervalUsage", pattern=QTY)
    start_on: date = Field(alias="startOn")


class PmPlanUpdate(ApiModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    checklist: str | None = Field(None, max_length=1000)
    trigger_kind: TriggerKind | None = Field(None, alias="triggerKind")
    interval_days: int | None = Field(None, alias="intervalDays", ge=1, le=365)
    interval_usage: str | None = Field(None, alias="intervalUsage", pattern=QTY)
    is_active: bool | None = Field(None, alias="isActive")


class ChecklistItemBody(ApiModel):
    id: int | None = None
    name: str = Field(min_length=1, max_length=100)
    method: CheckMethod
    standard_text: str | None = Field(None, alias="standardText", max_length=200)
    lower_limit: str | None = Field(None, alias="lowerLimit", pattern=NUMBER)
    upper_limit: str | None = Field(None, alias="upperLimit", pattern=NUMBER)
    unit: str | None = Field(None, max_length=10)
    is_active: bool | None = Field(None, alias="isActive")


class CheckEntry(ApiModel):
    checklist_item_id: int = Field(alias="checklistItemId")
    result: Literal["OK", "NG"] | None = None
    measured_value: str | None = Field(None, alias="measuredValue", pattern=NUMBER)
    note: str | None = Field(None, max_length=300)


class ChecksBody(ApiModel):
    checks: list[CheckEntry] = Field(min_length=1, max_length=50)


class PartUsageCreate(ApiModel):
    spare_part_id: int = Field(alias="sparePartId")
    qty: str = Field(pattern=QTY)
    unit_cost: str | None = Field(None, alias="unitCost", pattern=MONEY)


class SparePartCreate(ApiModel):
    code: str = Field(pattern=CODE)
    name: str = Field(min_length=1, max_length=100)
    unit: str = Field(min_length=1, max_length=10)
    safety_stock: str = Field("0", alias="safetyStock", pattern=QTY)
    item_code: str | None = Field(None, alias="itemCode", max_length=40)
    unit_cost: str | None = Field(None, alias="unitCost", pattern=MONEY)


class SparePartUpdate(ApiModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    unit: str | None = Field(None, min_length=1, max_length=10)
    safety_stock: str | None = Field(None, alias="safetyStock", pattern=QTY)
    item_code: str | None = Field(None, alias="itemCode", max_length=40)
    unit_cost: str | None = Field(None, alias="unitCost", pattern=MONEY)
    is_active: bool | None = Field(None, alias="isActive")
