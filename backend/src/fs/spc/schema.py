"""SPC 요청 본문 (FS-028 모듈 설계 8장). 수치는 문자열로 받아 Decimal로 다룬다."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

CODE = r"^[A-Z][A-Z0-9-]{1,19}$"
NUMBER = r"^-?\d{1,8}(\.\d{1,4})?$"  # numeric(12,4)
Cause = Literal["MACHINE", "MATERIAL", "MAN", "METHOD", "MEASUREMENT", "ENVIRONMENT"]
ChartType = Literal["XBAR_R", "I_MR"]  # 계수형(P·NP·C·U)은 MES 실적 계약이 선행한다
Rules = list[Annotated[int, Field(ge=1, le=8)]]  # Nelson 판정 규칙 번호


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class CharacteristicCreate(ApiModel):
    code: str = Field(pattern=CODE)
    item_code: str = Field(alias="itemCode", min_length=1, max_length=40)
    process_code: str = Field(alias="processCode", min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    unit: str = Field(min_length=1, max_length=10)
    lsl: str | None = Field(None, pattern=NUMBER)
    usl: str | None = Field(None, pattern=NUMBER)
    target: str | None = Field(None, pattern=NUMBER)
    decimals: int = Field(3, ge=0, le=4)
    chart_type: ChartType = Field("XBAR_R", alias="chartType")
    subgroup_size: int = Field(5, alias="subgroupSize", ge=1, le=10)
    rules: Rules | None = Field(None, max_length=8)


class CharacteristicUpdate(ApiModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    unit: str | None = Field(None, min_length=1, max_length=10)
    lsl: str | None = Field(None, pattern=NUMBER)
    usl: str | None = Field(None, pattern=NUMBER)
    target: str | None = Field(None, pattern=NUMBER)
    decimals: int | None = Field(None, ge=0, le=4)
    is_active: bool | None = Field(None, alias="isActive")
    chart_type: ChartType | None = Field(None, alias="chartType")
    subgroup_size: int | None = Field(None, alias="subgroupSize", ge=1, le=10)
    rules: Rules | None = Field(None, max_length=8)


class LimitPublish(ApiModel):
    basis_from: datetime = Field(alias="basisFrom")
    basis_to: datetime = Field(alias="basisTo")
    reason: str = Field(min_length=2, max_length=200)


class SubgroupCreate(ApiModel):
    characteristic_id: int = Field(alias="characteristicId")
    lot_no: str = Field(alias="lotNo", min_length=1, max_length=50)
    measured_at: datetime = Field(alias="measuredAt")
    # 개수는 특성의 부분군 크기와 같아야 한다(서비스가 확인한다).
    values: list[str] = Field(min_length=1, max_length=10)
    note: str | None = Field(None, max_length=300)


class OcapItemCreate(ApiModel):
    characteristic_id: int | None = Field(None, alias="characteristicId")
    rule_no: int | None = Field(None, alias="ruleNo", ge=1, le=8)
    seq: int = Field(ge=1, le=99)
    check_text: str = Field(alias="checkText", min_length=2, max_length=300)
    cause_category: Cause | None = Field(None, alias="causeCategory")


class OcapItemUpdate(ApiModel):
    characteristic_id: int | None = Field(None, alias="characteristicId")
    rule_no: int | None = Field(None, alias="ruleNo", ge=1, le=8)
    seq: int | None = Field(None, ge=1, le=99)
    check_text: str | None = Field(
        None, alias="checkText", min_length=2, max_length=300
    )
    cause_category: Cause | None = Field(None, alias="causeCategory")
    is_active: bool | None = Field(None, alias="isActive")


class OcapCheckEntry(ApiModel):
    ocap_item_id: int = Field(alias="ocapItemId")
    result: Literal["OK", "NG", "NA"]
    note: str | None = Field(None, max_length=300)


class OcapChecks(ApiModel):
    checks: list[OcapCheckEntry] = Field(min_length=1, max_length=50)


class ReportCreate(ApiModel):
    characteristic_id: int = Field(alias="characteristicId")
    report_start_on: date = Field(alias="reportStartOn")
    report_end_on: date = Field(alias="reportEndOn")
    comment: str | None = Field(None, max_length=1000)


class ReportConfirm(ApiModel):
    comment: str | None = Field(None, max_length=1000)


class VoidBody(ApiModel):
    reason: str = Field(min_length=2, max_length=200)


class Resolve(ApiModel):
    cause_category: Cause = Field(alias="causeCategory")
    action: str = Field(min_length=2, max_length=500)
