"""FS-026b1 inputs. FastAPI's shared handler maps validation to HTTP 400."""

from datetime import date
from typing import Literal

from pydantic import Field

from fs.wms.schema import QTY, ApiModel

NoticeStatus = Literal["PLANNED", "ARRIVED", "INSPECTED", "CANCELLED"]
NoticeKind = Literal["PURCHASE", "PO", "SALES_RETURN", "SUBCONTRACT"]


class NoticeLine(ApiModel):
    item_id: int = Field(alias="itemId", gt=0)
    lot_no: str | None = Field(None, alias="lotNo", min_length=1, max_length=50)
    expected_qty: str = Field(alias="expectedQty", pattern=QTY)
    normal_location_id: int = Field(alias="normalLocationId", gt=0)
    quarantine_location_id: int | None = Field(None, alias="quarantineLocationId", gt=0)


class NoticeFields(ApiModel):
    warehouse_id: int = Field(alias="warehouseId", gt=0)
    expected_on: date = Field(alias="expectedOn")
    notice_kind: NoticeKind = Field("PURCHASE", alias="noticeKind")
    vehicle_no: str | None = Field(None, alias="vehicleNo", max_length=40)
    partner_ref: str | None = Field(None, alias="partnerRef", max_length=100)
    lines: list[NoticeLine] = Field(min_length=1, max_length=100)


class NoticeCreate(NoticeFields):
    business_key: str = Field(alias="businessKey", min_length=1, max_length=100)


class VersionInput(ApiModel):
    expected_version: int = Field(alias="expectedVersion", gt=0)


class NoticeUpdate(NoticeFields, VersionInput):
    pass


class SourceLink(VersionInput):
    source_key: str = Field(
        alias="sourceKey", pattern=r"^ERP:PURCHASE:.+$", max_length=100
    )


class ReasonInput(VersionInput):
    reason: str = Field(min_length=1, max_length=300)


class InspectionLine(ApiModel):
    line_id: int = Field(alias="lineId", gt=0)
    accepted_qty: str = Field(alias="acceptedQty", pattern=QTY)
    quarantined_qty: str = Field(alias="quarantinedQty", pattern=QTY)
    shortage_qty: str = Field(alias="shortageQty", pattern=QTY)
    reason: str | None = Field(None, max_length=300)


class InspectionInput(VersionInput):
    lines: list[InspectionLine] = Field(min_length=1, max_length=100)
