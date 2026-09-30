"""FS-026b2 reservation requests; shared handler produces HTTP 400."""

from typing import Literal

from pydantic import Field

from fs.wms.receiving_schema import VersionInput
from fs.wms.schema import QTY, ApiModel

ReservationStatus = Literal["ACTIVE", "RELEASED", "CONSUMED"]


class ReservationLine(ApiModel):
    item_id: int = Field(alias="itemId", gt=0)
    location_id: int = Field(alias="locationId", gt=0)
    lot_no: str | None = Field(None, alias="lotNo", min_length=1, max_length=50)
    quantity: str = Field(pattern=QTY)


class ReservationCreate(ApiModel):
    business_key: str = Field(alias="businessKey", min_length=1, max_length=100)
    shipment_order_ref: str | None = Field(
        None, alias="shipmentOrderRef", min_length=1, max_length=40
    )
    reason: str | None = Field(None, max_length=300)
    lines: list[ReservationLine] = Field(min_length=1, max_length=100)


class ConsumeShipment(VersionInput):
    source_key: str = Field(
        alias="sourceKey", pattern=r"^ERP:SHIPMENT:.+$", max_length=100
    )
