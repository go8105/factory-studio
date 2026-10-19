"""W2b-1g 라벨 출력(W-17) 요청 본문 (DSN-13 F07·F13)."""

from typing import Literal

from pydantic import Field

from fs.wms.schema import ApiModel

LabelKind = Literal["LOCATION", "MATERIAL_LOT"]
LabelStatus = Literal["VALID", "VOID"]


class LabelPrint(ApiModel):
    label_kind: LabelKind = Field(alias="labelKind")
    barcode_value: str = Field(alias="barcodeValue", min_length=1, max_length=80)
    copies: int = Field(default=1, ge=1, le=99)
    reprint_reason: str | None = Field(
        default=None, alias="reprintReason", max_length=300
    )
