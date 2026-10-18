"""W2b-1e 생산 불출(W-13) 요청 본문 (DSN-13 F25, Q4)."""

from typing import Literal

from pydantic import Field

from fs.wms.schema import QTY, ApiModel

IssueRequestStatus = Literal["OPEN", "ISSUED", "CANCELLED"]


class IssueLineIn(ApiModel):
    item_id: int = Field(alias="itemId", gt=0)
    qty: str = Field(pattern=QTY)


class IssueRequestCreate(ApiModel):
    line_location_id: int = Field(alias="lineLocationId", gt=0)
    work_order_no: str | None = Field(default=None, alias="workOrderNo", max_length=40)
    needed_at: str | None = Field(default=None, alias="neededAt")
    lines: list[IssueLineIn] = Field(min_length=1, max_length=100)


class IssueLineConfirm(ApiModel):
    line_id: int = Field(alias="lineId", gt=0)
    issued_qty: str = Field(alias="issuedQty", pattern=QTY)


class IssueRequestConfirm(ApiModel):
    lines: list[IssueLineConfirm] | None = Field(default=None, max_length=100)


class IssueRequestCancel(ApiModel):
    cancel_reason: str = Field(alias="cancelReason", min_length=1, max_length=300)
