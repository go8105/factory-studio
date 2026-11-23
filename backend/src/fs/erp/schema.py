from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Code = Annotated[str, Field(min_length=1, max_length=40)]
Unit = Literal["EA", "BOX", "KG", "M", "L", "SET"]
Month = Annotated[str, Field(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")]
Money = Annotated[str, Field(pattern=r"^\d{1,16}(\.\d{1,2})?$")]  # numeric(18,2)
UnitPrice = Annotated[str, Field(pattern=r"^\d{1,14}(\.\d{1,4})?$")]  # numeric(18,4)


class ApiModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", populate_by_name=True, str_strip_whitespace=True
    )


# DSN-11 F02·F03: 구분에 BOTH(매출·매입 둘 다), 상세·여신·단가 그룹 추가
PartnerKind = Literal["CUSTOMER", "SUPPLIER", "BOTH"]
BusinessNo = Annotated[str, Field(pattern=r"^[0-9]{3}-[0-9]{2}-[0-9]{5}$")]
# DSN-11 F05: 품목 구분에 상품(merchandise)·무형(intangible) 추가
ItemType = Literal[
    "finished", "semi_finished", "raw", "auxiliary", "merchandise", "intangible"
]


class PartnerDetail(ApiModel):
    """상세·여신·단가 그룹. 전부 비울 수 있다(옛 공간에는 값이 없다)."""

    business_no: BusinessNo | None = Field(None, alias="businessNo")
    representative: str | None = Field(None, min_length=1, max_length=60)
    business_type: str | None = Field(
        None, alias="businessType", min_length=1, max_length=60
    )
    business_item: str | None = Field(
        None, alias="businessItem", min_length=1, max_length=60
    )
    address: str | None = Field(None, min_length=1, max_length=300)
    phone: str | None = Field(None, min_length=1, max_length=30)
    contact_name: str | None = Field(
        None, alias="contactName", min_length=1, max_length=60
    )
    partner_group: str | None = Field(
        None, alias="partnerGroup", min_length=1, max_length=40
    )
    credit_limit: Money | None = Field(None, alias="creditLimit")
    credit_days: int | None = Field(None, alias="creditDays", ge=0, le=2147483647)
    sale_price_group_id: int | None = Field(None, alias="salePriceGroupId", gt=0)
    purchase_price_group_id: int | None = Field(
        None, alias="purchasePriceGroupId", gt=0
    )


class PartnerCreate(PartnerDetail):
    partner_code: Code = Field(alias="partnerCode")
    partner_name: str = Field(alias="partnerName", min_length=1, max_length=200)
    partner_kind: PartnerKind = Field(alias="partnerKind")
    payment_term_days: int | None = Field(
        None, alias="paymentTermDays", ge=0, le=2147483647
    )
    is_active: bool = Field(True, alias="isActive")


class PartnerUpdate(PartnerDetail):
    partner_code: Code | None = Field(None, alias="partnerCode")
    partner_name: str | None = Field(
        None, alias="partnerName", min_length=1, max_length=200
    )
    partner_kind: PartnerKind | None = Field(None, alias="partnerKind")
    payment_term_days: int | None = Field(
        None, alias="paymentTermDays", ge=0, le=2147483647
    )
    is_active: bool | None = Field(None, alias="isActive")


class ItemCreate(ApiModel):
    item_code: Code = Field(alias="itemCode")
    name: str = Field(min_length=1, max_length=100)
    base_unit: Unit = Field("EA", alias="baseUnit")
    item_type: ItemType = Field("finished", alias="itemType")
    tax_category: Literal["TAXABLE", "ZERO", "EXEMPT"] = Field(alias="taxCategory")
    is_active: bool = Field(True, alias="isActive")
    spec: str | None = Field(None, min_length=1, max_length=100)
    standard_cost: UnitPrice | None = Field(None, alias="standardCost")
    standard_price: UnitPrice | None = Field(None, alias="standardPrice")
    track_stock: bool = Field(True, alias="trackStock")


class ItemUpdate(ApiModel):
    item_code: Code | None = Field(None, alias="itemCode")
    name: str | None = Field(None, min_length=1, max_length=100)
    base_unit: Unit | None = Field(None, alias="baseUnit")
    item_type: ItemType | None = Field(None, alias="itemType")
    tax_category: Literal["TAXABLE", "ZERO", "EXEMPT"] | None = Field(
        None, alias="taxCategory"
    )
    is_active: bool | None = Field(None, alias="isActive")
    spec: str | None = Field(None, min_length=1, max_length=100)
    standard_cost: UnitPrice | None = Field(None, alias="standardCost")
    standard_price: UnitPrice | None = Field(None, alias="standardPrice")
    track_stock: bool | None = Field(None, alias="trackStock")


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


# ---- DSN-11 1c 기초등록: 부서·담당자·프로젝트·단가 그룹·계정 ----
# DB CHECK와 같은 모양이다. 여기서 막으면 DB 오류 대신 필드별 메시지가 나간다.
MasterCode = Annotated[str, Field(pattern=r"^[A-Z0-9][A-Z0-9_-]{0,29}$")]
CostCenter = Literal["MFG", "SALES", "ADMIN"]
AccountClass = Literal[
    "ASSET",
    "LIABILITY",
    "EQUITY",
    "REVENUE",
    "COGS",
    "EXPENSE",
    "MFG_COST",
    "NON_OPERATING",
]


class DepartmentCreate(ApiModel):
    code: MasterCode
    name: str = Field(min_length=1, max_length=100)
    cost_center_kind: CostCenter = Field("ADMIN", alias="costCenterKind")
    is_active: bool = Field(True, alias="isActive")


class DepartmentUpdate(ApiModel):
    code: MasterCode | None = None
    name: str | None = Field(None, min_length=1, max_length=100)
    cost_center_kind: CostCenter | None = Field(None, alias="costCenterKind")
    is_active: bool | None = Field(None, alias="isActive")


class EmployeeCreate(ApiModel):
    code: MasterCode
    name: str = Field(min_length=1, max_length=100)
    department_id: int = Field(alias="departmentId", gt=0)
    hr_employee_code: str | None = Field(
        None, alias="hrEmployeeCode", min_length=1, max_length=30
    )
    is_active: bool = Field(True, alias="isActive")


class EmployeeUpdate(ApiModel):
    code: MasterCode | None = None
    name: str | None = Field(None, min_length=1, max_length=100)
    department_id: int | None = Field(None, alias="departmentId", gt=0)
    hr_employee_code: str | None = Field(
        None, alias="hrEmployeeCode", min_length=1, max_length=30
    )
    is_active: bool | None = Field(None, alias="isActive")


class ProjectCreate(ApiModel):
    code: MasterCode
    name: str = Field(min_length=1, max_length=200)
    start_on: date | None = Field(None, alias="startOn")
    end_on: date | None = Field(None, alias="endOn")
    is_active: bool = Field(True, alias="isActive")


class ProjectUpdate(ApiModel):
    code: MasterCode | None = None
    name: str | None = Field(None, min_length=1, max_length=200)
    start_on: date | None = Field(None, alias="startOn")
    end_on: date | None = Field(None, alias="endOn")
    is_active: bool | None = Field(None, alias="isActive")


class PriceGroupCreate(ApiModel):
    code: MasterCode
    name: str = Field(min_length=1, max_length=100)
    price_kind: Literal["SALE", "PURCHASE"] = Field("SALE", alias="priceKind")
    is_active: bool = Field(True, alias="isActive")


class PriceGroupUpdate(ApiModel):
    code: MasterCode | None = None
    name: str | None = Field(None, min_length=1, max_length=100)
    price_kind: Literal["SALE", "PURCHASE"] | None = Field(None, alias="priceKind")
    is_active: bool | None = Field(None, alias="isActive")


class GroupPriceCreate(ApiModel):
    price_group_id: int = Field(alias="priceGroupId", gt=0)
    item_id: int = Field(alias="itemId", gt=0)
    unit_price: UnitPrice = Field(alias="unitPrice")
    currency: Literal["KRW"] = "KRW"
    valid_from: date = Field(alias="validFrom")


class GroupPriceUpdate(ApiModel):
    price_group_id: int | None = Field(None, alias="priceGroupId", gt=0)
    item_id: int | None = Field(None, alias="itemId", gt=0)
    unit_price: UnitPrice | None = Field(None, alias="unitPrice")
    currency: Literal["KRW"] | None = None
    valid_from: date | None = Field(None, alias="validFrom")


class AccountCreate(ApiModel):
    account_code: MasterCode = Field(alias="accountCode")
    account_name: str = Field(alias="accountName", min_length=1, max_length=100)
    account_class: AccountClass = Field(alias="accountClass")
    normal_side: Literal["DEBIT", "CREDIT"] = Field(alias="normalSide")
    statement_group: str | None = Field(
        None, alias="statementGroup", min_length=1, max_length=40
    )
    requires_partner: bool = Field(False, alias="requiresPartner")
    requires_department: bool = Field(False, alias="requiresDepartment")
    is_active: bool = Field(True, alias="isActive")


class AccountUpdate(ApiModel):
    account_name: str | None = Field(
        None, alias="accountName", min_length=1, max_length=100
    )
    account_class: AccountClass | None = Field(None, alias="accountClass")
    normal_side: Literal["DEBIT", "CREDIT"] | None = Field(None, alias="normalSide")
    statement_group: str | None = Field(
        None, alias="statementGroup", min_length=1, max_length=40
    )
    requires_partner: bool | None = Field(None, alias="requiresPartner")
    requires_department: bool | None = Field(None, alias="requiresDepartment")
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


# ---- FS-019f 매입·지급 ----
class PaymentCreate(ApiModel):
    payment_no: Code = Field(alias="paymentNo")
    partner_id: int = Field(alias="partnerId", gt=0)
    paid_on: date = Field(alias="paidOn")
    amount: Money


class PaymentUpdate(ApiModel):
    payment_no: Code | None = Field(None, alias="paymentNo")
    partner_id: int | None = Field(None, alias="partnerId", gt=0)
    paid_on: date | None = Field(None, alias="paidOn")
    amount: Money | None = None


class PaymentApplicationIn(ApiModel):
    payable_id: int = Field(alias="payableId", gt=0)
    amount: Money


class PaymentApplications(ApiModel):
    lines: list[PaymentApplicationIn] = Field(min_length=1, max_length=200)


class PurchaseLineIn(ApiModel):
    item_id: int = Field(alias="itemId", gt=0)
    quantity: Qty
    unit: str = Field(min_length=1, max_length=10)
    unit_price: Price = Field(alias="unitPrice")


InvoiceKind = Literal["PO_RECEIPT", "DIRECT", "SUBCONTRACT"]


class PurchaseInvoiceCreate(ApiModel):
    invoice_no: Code = Field(alias="invoiceNo")
    partner_id: int = Field(alias="partnerId", gt=0)
    invoice_date: date = Field(alias="invoiceDate")
    due_date: date | None = Field(None, alias="dueDate")  # 비우면 확정 때 결제조건
    invoice_kind: InvoiceKind = Field("DIRECT", alias="invoiceKind")
    purchase_order_id: int | None = Field(None, alias="purchaseOrderId", gt=0)
    source_ref: str | None = Field(None, alias="sourceRef", min_length=1, max_length=60)
    department_id: int | None = Field(None, alias="departmentId", gt=0)
    project_id: int | None = Field(None, alias="projectId", gt=0)


class PurchaseInvoiceUpdate(ApiModel):
    invoice_no: Code | None = Field(None, alias="invoiceNo")
    partner_id: int | None = Field(None, alias="partnerId", gt=0)
    invoice_date: date | None = Field(None, alias="invoiceDate")
    due_date: date | None = Field(None, alias="dueDate")


class PurchaseLines(ApiModel):
    lines: list[PurchaseLineIn] = Field(max_length=200)


# ---- DSN-11 1d 구매: 요청 · 발주 ----
class RequestLineIn(ApiModel):
    item_id: int = Field(alias="itemId", gt=0)
    quantity: Qty
    unit: str | None = Field(None, min_length=1, max_length=10)
    needed_on: date | None = Field(None, alias="neededOn")


class PurchaseRequestCreate(ApiModel):
    requested_on: date = Field(alias="requestedOn")
    department_id: int | None = Field(None, alias="departmentId", gt=0)
    employee_id: int | None = Field(None, alias="employeeId", gt=0)
    # 수동 말고는 아직 만드는 쪽이 없다(CMMS에 요청 표가 없다 — ERP-1b).
    source: Literal["MANUAL", "CMMS", "ELB", "MES"] = "MANUAL"
    source_ref: str | None = Field(None, alias="sourceRef", min_length=1, max_length=60)


class RequestLines(ApiModel):
    lines: list[RequestLineIn] = Field(max_length=200)


class PurchaseOrderLineIn(ApiModel):
    item_id: int = Field(alias="itemId", gt=0)
    quantity: Qty
    unit: str | None = Field(None, min_length=1, max_length=10)
    unit_price: Price | None = Field(None, alias="unitPrice")
    due_on: date | None = Field(None, alias="dueOn")


class PurchaseOrderCreate(ApiModel):
    partner_id: int = Field(alias="partnerId", gt=0)
    ordered_on: date = Field(alias="orderedOn")
    due_on: date | None = Field(None, alias="dueOn")
    department_id: int | None = Field(None, alias="departmentId", gt=0)
    project_id: int | None = Field(None, alias="projectId", gt=0)


class PurchaseOrderLines(ApiModel):
    lines: list[PurchaseOrderLineIn] = Field(max_length=200)


class LoadRequestIn(ApiModel):
    request_id: int = Field(alias="requestId", gt=0)


# ---- DSN-11 1e 회계: 전표 · 미반영 · 지출결의 ----
class JournalLineIn(ApiModel):
    account_id: int = Field(alias="accountId", gt=0)
    side: Literal["DEBIT", "CREDIT"]
    amount: Money
    partner_id: int | None = Field(None, alias="partnerId", gt=0)
    department_id: int | None = Field(None, alias="departmentId", gt=0)
    project_id: int | None = Field(None, alias="projectId", gt=0)
    memo: str | None = Field(None, min_length=1, max_length=300)


class JournalEntryCreate(ApiModel):
    entry_date: date = Field(alias="entryDate")
    description: str | None = Field(None, min_length=1, max_length=300)
    department_id: int | None = Field(None, alias="departmentId", gt=0)


class JournalLines(ApiModel):
    lines: list[JournalLineIn] = Field(max_length=200)


class ReverseIn(ApiModel):
    reason: Reason


class PendingTarget(ApiModel):
    source_kind: str = Field(alias="sourceKind", min_length=1, max_length=30)
    entry_kind: str = Field(alias="entryKind", min_length=1, max_length=16)
    source_id: int = Field(alias="sourceId", gt=0)


class PendingPost(ApiModel):
    targets: list[PendingTarget] = Field(max_length=500)


class ExpenseLineIn(ApiModel):
    account_id: int = Field(alias="accountId", gt=0)
    amount: Money
    project_id: int | None = Field(None, alias="projectId", gt=0)
    memo: str | None = Field(None, min_length=1, max_length=300)


class ExpenseClaimCreate(ApiModel):
    claimed_on: date = Field(alias="claimedOn")
    employee_id: int = Field(alias="employeeId", gt=0)
    department_id: int = Field(alias="departmentId", gt=0)
    pay_method: Literal["BANK", "CARD", "CASH"] = Field("BANK", alias="payMethod")
    # 합계 > 0이 DB 제약이라 결의서는 명세 한 줄과 함께 태어난다.
    lines: list[ExpenseLineIn] = Field(min_length=1, max_length=200)


class ExpenseLines(ApiModel):
    lines: list[ExpenseLineIn] = Field(max_length=200)


# ---- DSN-11 1d 반품(판매·구매 공통) ----
class ReturnLineIn(ApiModel):
    item_id: int = Field(alias="itemId", gt=0)
    quantity: Qty


class ReturnLines(ApiModel):
    lines: list[ReturnLineIn] = Field(max_length=200)


class SalesReturnCreate(ApiModel):
    partner_id: int = Field(alias="partnerId", gt=0)
    sales_record_id: int = Field(alias="salesRecordId", gt=0)
    returned_on: date = Field(alias="returnedOn")
    reason: Reason


class PurchaseReturnCreate(ApiModel):
    partner_id: int = Field(alias="partnerId", gt=0)
    purchase_invoice_id: int = Field(alias="purchaseInvoiceId", gt=0)
    returned_on: date = Field(alias="returnedOn")
    reason: Reason


# ---- DSN-11 1f 장부·결산: E-35 기초 잔액·월 마감 ----
Year = Annotated[str, Field(pattern=r"^[0-9]{4}$")]


class OpeningBalanceCreate(ApiModel):
    fiscal_year: Year = Field(alias="fiscalYear")
    account_id: int = Field(alias="accountId", gt=0)
    partner_id: int | None = Field(None, alias="partnerId", gt=0)
    side: Literal["DEBIT", "CREDIT"]
    amount: Money


class OpeningBalanceUpdate(ApiModel):
    partner_id: int | None = Field(None, alias="partnerId", gt=0)
    side: Literal["DEBIT", "CREDIT"] | None = None
    amount: Money | None = None


class CarryForwardIn(ApiModel):
    fiscal_year: Year = Field(alias="fiscalYear")
