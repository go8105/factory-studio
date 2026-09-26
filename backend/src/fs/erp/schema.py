from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Code = Annotated[str, Field(min_length=1, max_length=40)]
Unit = Literal["EA", "BOX", "KG", "M", "L", "SET"]
Month = Annotated[str, Field(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")]


class ApiModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", populate_by_name=True, str_strip_whitespace=True
    )


class PartnerCreate(ApiModel):
    partner_code: Code = Field(alias="partnerCode")
    partner_name: str = Field(alias="partnerName", min_length=1, max_length=200)
    partner_kind: Literal["CUSTOMER", "SUPPLIER"] = Field(alias="partnerKind")
    payment_term_days: int | None = Field(
        None, alias="paymentTermDays", ge=0, le=2147483647
    )
    is_active: bool = Field(True, alias="isActive")


class PartnerUpdate(ApiModel):
    partner_code: Code | None = Field(None, alias="partnerCode")
    partner_name: str | None = Field(
        None, alias="partnerName", min_length=1, max_length=200
    )
    partner_kind: Literal["CUSTOMER", "SUPPLIER"] | None = Field(
        None, alias="partnerKind"
    )
    payment_term_days: int | None = Field(
        None, alias="paymentTermDays", ge=0, le=2147483647
    )
    is_active: bool | None = Field(None, alias="isActive")


class ItemCreate(ApiModel):
    item_code: Code = Field(alias="itemCode")
    name: str = Field(min_length=1, max_length=100)
    base_unit: Unit = Field("EA", alias="baseUnit")
    item_type: Literal["finished", "semi_finished", "raw", "auxiliary"] = Field(
        "finished", alias="itemType"
    )
    tax_category: Literal["TAXABLE", "ZERO", "EXEMPT"] = Field(alias="taxCategory")
    is_active: bool = Field(True, alias="isActive")


class ItemUpdate(ApiModel):
    item_code: Code | None = Field(None, alias="itemCode")
    name: str | None = Field(None, min_length=1, max_length=100)
    base_unit: Unit | None = Field(None, alias="baseUnit")
    item_type: Literal["finished", "semi_finished", "raw", "auxiliary"] | None = Field(
        None, alias="itemType"
    )
    tax_category: Literal["TAXABLE", "ZERO", "EXEMPT"] | None = Field(
        None, alias="taxCategory"
    )
    is_active: bool | None = Field(None, alias="isActive")


class ConversionCreate(ApiModel):
    from_unit: str = Field(alias="fromUnit", min_length=1, max_length=10)
    factor: str = Field(pattern=r"^\d{1,12}(\.\d{1,6})?$")


class ConversionUpdate(ApiModel):
    from_unit: str | None = Field(None, alias="fromUnit", min_length=1, max_length=10)
    factor: str | None = Field(None, pattern=r"^\d{1,12}(\.\d{1,6})?$")


class PriceCreate(ApiModel):
    partner_id: int = Field(alias="partnerId", gt=0)
    item_id: int = Field(alias="itemId", gt=0)
    price_kind: str = Field("SALE", alias="priceKind", min_length=1, max_length=20)
    unit_price: str = Field(alias="unitPrice", pattern=r"^\d{1,14}(\.\d{1,4})?$")
    currency: str = Field("KRW", pattern=r"^[A-Z]{3}$")
    effective_from: Month = Field(alias="effectiveFrom")
    effective_to: Month | None = Field(None, alias="effectiveTo")
    is_active: bool = Field(True, alias="isActive")


class PriceUpdate(ApiModel):
    partner_id: int | None = Field(None, alias="partnerId", gt=0)
    item_id: int | None = Field(None, alias="itemId", gt=0)
    price_kind: str | None = Field(None, alias="priceKind", min_length=1, max_length=20)
    unit_price: str | None = Field(
        None, alias="unitPrice", pattern=r"^\d{1,14}(\.\d{1,4})?$"
    )
    currency: str | None = Field(None, pattern=r"^[A-Z]{3}$")
    effective_from: Month | None = Field(None, alias="effectiveFrom")
    effective_to: Month | None = Field(None, alias="effectiveTo")
    is_active: bool | None = Field(None, alias="isActive")


# ---- FS-019b 영업: 견적·판매계획·수주 ----
Qty = Annotated[str, Field(pattern=r"^\d{1,15}(\.\d{1,3})?$")]  # numeric(18,3)
Price = Annotated[str, Field(pattern=r"^\d{1,14}(\.\d{1,4})?$")]  # numeric(18,4)
Rate = Annotated[str, Field(pattern=r"^\d{1,3}(\.\d{1,2})?$")]  # 0~100은 서비스
Reason = Annotated[str, Field(min_length=1, max_length=200)]


class QuotationCreate(ApiModel):
    quote_no: Code = Field(alias="quoteNo")
    partner_id: int = Field(alias="partnerId", gt=0)
    quoted_on: date = Field(alias="quotedOn")
    valid_until: date | None = Field(None, alias="validUntil")
    remark: str | None = Field(None, max_length=1000)


class QuotationUpdate(ApiModel):
    partner_id: int | None = Field(None, alias="partnerId", gt=0)
    quoted_on: date | None = Field(None, alias="quotedOn")
    valid_until: date | None = Field(None, alias="validUntil")
    remark: str | None = Field(None, max_length=1000)


class QuotationLineIn(ApiModel):
    item_id: int = Field(alias="itemId", gt=0)
    quote_qty: Qty = Field(alias="quoteQty")
    unit_price: Price | None = Field(None, alias="unitPrice")  # 비우면 거래처 단가
    discount_rate: Rate = Field("0", alias="discountRate")


class QuotationLines(ApiModel):
    lines: list[QuotationLineIn] = Field(max_length=200)


class QuotationStatus(ApiModel):
    status: Literal["confirmed", "sent", "accepted", "rejected", "cancelled"]
    reason: Reason | None = None


class QuotationConvert(ApiModel):
    order_no: Code = Field(alias="orderNo")
    ordered_on: date = Field(alias="orderedOn")
    due_on: date = Field(alias="dueOn")


class SalesPlanCreate(ApiModel):
    plan_code: Code = Field(alias="planCode")
    target_month: Month = Field(alias="targetMonth")


class SalesPlanUpdate(ApiModel):
    plan_code: Code | None = Field(None, alias="planCode")
    target_month: Month | None = Field(None, alias="targetMonth")


class SalesPlanLineIn(ApiModel):
    item_id: int = Field(alias="itemId", gt=0)
    plan_qty: Qty = Field(alias="planQty")


class SalesPlanLines(ApiModel):
    lines: list[SalesPlanLineIn] = Field(max_length=200)


class OrderLineIn(ApiModel):
    item_id: int = Field(alias="itemId", gt=0)
    order_qty: Qty = Field(alias="orderQty")
    unit_price: Price | None = Field(None, alias="unitPrice")  # 비우면 거래처 단가


class SalesOrderCreate(ApiModel):
    order_no: Code = Field(alias="orderNo")
    partner_id: int = Field(alias="partnerId", gt=0)
    ordered_on: date = Field(alias="orderedOn")
    due_on: date = Field(alias="dueOn")
    lines: list[OrderLineIn] = Field(min_length=1, max_length=200)


class SalesOrderUpdate(ApiModel):
    partner_id: int | None = Field(None, alias="partnerId", gt=0)
    ordered_on: date | None = Field(None, alias="orderedOn")
    due_on: date | None = Field(None, alias="dueOn")
    lines: list[OrderLineIn] | None = Field(None, min_length=1, max_length=200)


# ---- FS-019c 출하지시·출하 ----
class ShipOrderLineIn(ApiModel):
    sales_order_line_id: int = Field(alias="salesOrderLineId", gt=0)
    order_qty: Qty = Field(alias="orderQty")


class ShipOrderCreate(ApiModel):
    ship_order_no: Code = Field(alias="shipOrderNo")
    sales_order_id: int = Field(alias="salesOrderId", gt=0)
    ordered_on: date = Field(alias="orderedOn")
    lines: list[ShipOrderLineIn] = Field(min_length=1, max_length=200)


class CancelIn(ApiModel):
    reason: str = Field(min_length=1, max_length=300)


class ShipmentLineIn(ApiModel):
    shipment_order_line_id: int = Field(alias="shipmentOrderLineId", gt=0)
    packing_no: str | None = Field(None, alias="packingNo", max_length=40)


class ShipmentCreate(ApiModel):
    shipment_no: Code = Field(alias="shipmentNo")
    shipment_order_id: int = Field(alias="shipmentOrderId", gt=0)
    lines: list[ShipmentLineIn] = Field([], max_length=200)  # 패킹번호만. 수량은 서버


# ---- FS-019d 매출·세금계산서 ----
class TaxInvoiceCreate(ApiModel):
    sales_record_id: int = Field(alias="salesRecordId", gt=0)


class TaxInvoiceIssue(ApiModel):
    approval_no: str = Field(alias="approvalNo", min_length=1, max_length=60)
    issued_on: date = Field(alias="issuedOn")


# ---- FS-019e 수금·소명 ----
Money = Annotated[str, Field(pattern=r"^\d{1,16}(\.\d{1,2})?$")]  # numeric(18,2)


class ReceiptCreate(ApiModel):
    receipt_no: Code = Field(alias="receiptNo")
    partner_id: int = Field(alias="partnerId", gt=0)
    received_on: date = Field(alias="receivedOn")
    amount: Money


class ReceiptUpdate(ApiModel):
    receipt_no: Code | None = Field(None, alias="receiptNo")
    partner_id: int | None = Field(None, alias="partnerId", gt=0)
    received_on: date | None = Field(None, alias="receivedOn")
    amount: Money | None = None


class ApplicationIn(ApiModel):
    receivable_id: int = Field(alias="receivableId", gt=0)
    amount: Money


class Applications(ApiModel):
    lines: list[ApplicationIn] = Field(min_length=1, max_length=200)
