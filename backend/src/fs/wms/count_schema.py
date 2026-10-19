"""W2b-1f 재고 실사(W-14)·재고 마감(W-15) 요청 본문 (DSN-13 F35·F39, Q6)."""

from typing import Literal

from pydantic import Field

from fs.wms.schema import QTY, ApiModel

MONTH = r"^[0-9]{4}-(0[1-9]|1[0-2])$"

CountKind = Literal["FULL", "CYCLE"]
CountStatus = Literal["OPEN", "COUNTED", "ADJUSTED", "CANCELLED"]


class CountOrderCreate(ApiModel):
    warehouse_id: int = Field(alias="warehouseId", gt=0)
    kind: CountKind = "FULL"
    location_ids: list[int] | None = Field(
        default=None, alias="locationIds", max_length=200
    )


class CountLineIn(ApiModel):
    line_id: int = Field(alias="lineId", gt=0)
    counted_qty: str = Field(alias="countedQty", pattern=QTY)


class CountOrderCount(ApiModel):
    lines: list[CountLineIn] = Field(min_length=1, max_length=500)


class PeriodClose(ApiModel):
    period_month: str = Field(alias="periodMonth", pattern=MONTH)
