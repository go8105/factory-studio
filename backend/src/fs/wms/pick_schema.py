"""W2b-1d 피킹 지시(W-12) 요청 본문."""

from typing import Literal

from pydantic import Field

from fs.wms.schema import QTY, ApiModel

PickOrderStatus = Literal["OPEN", "PICKED", "CANCELLED"]


class PickOrderCreate(ApiModel):
    reservation_id: int = Field(alias="reservationId", gt=0)


class PickLineConfirm(ApiModel):
    line_id: int = Field(alias="lineId", gt=0)
    picked_qty: str = Field(alias="pickedQty", pattern=QTY)


class PickOrderConfirm(ApiModel):
    to_location_id: int = Field(alias="toLocationId", gt=0)
    lines: list[PickLineConfirm] = Field(min_length=1, max_length=100)


class PickOrderCancel(ApiModel):
    cancel_reason: str = Field(alias="cancelReason", min_length=1, max_length=300)
