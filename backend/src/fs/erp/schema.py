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
