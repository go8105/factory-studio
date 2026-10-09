"""FS-030 strict request contracts. IDs accept decimal strings; money stays decimal text."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Code = Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9-]{1,29}$")]
Id = Annotated[int, Field(gt=0, le=9223372036854775807)]
Role = Literal["STAFF", "MANAGER", "EXECUTIVE", "BOARD_ADMIN"]
Money = Annotated[str, StringConstraints(pattern=r"^\d{1,16}(\.\d{1,2})?$")]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=False)


class Version(Model):
    expected_version: int = Field(alias="expectedVersion", gt=0, strict=True)


class Actor(Model):
    acting_person_id: Id = Field(alias="actingPersonId")


class PersonCreate(Model):
    code: Code
    name: Text = Field(max_length=80)
    job_role: Role = Field(alias="jobRole")


class PersonUpdate(Version):
    name: Text = Field(max_length=80)
    job_role: Role = Field(alias="jobRole")
    is_active: bool = Field(alias="isActive", strict=True)


DocumentKind = Literal["GENERAL", "ERP_PURCHASE", "ERP_PO", "ERP_EXPENSE", "PLM_ECO"]
ParticipantRole = Literal["APPROVER", "CONSENT", "REFERENCE"]
Month = Annotated[str, StringConstraints(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]


class Step(Model):
    person_id: Id = Field(alias="personId")
    seq: Annotated[int, Field(ge=1, le=3, strict=True)] | None = None
    participant_role: ParticipantRole = Field("APPROVER", alias="participantRole")


class RouteCreate(Model):
    code: Code
    name: Text = Field(max_length=100)
    steps: list[Step] = Field(min_length=1, max_length=30)


class RouteUpdate(Version):
    name: Text = Field(max_length=100)
    is_active: bool = Field(alias="isActive", strict=True)
    steps: list[Step] = Field(min_length=1, max_length=30)


class DocumentCreate(Actor):
    title: Text = Field(max_length=200)
    body: Text = Field(max_length=10000)
    route_id: Id = Field(alias="routeId")
    kind: DocumentKind
    source_no: Text | None = Field(None, alias="sourceNo", max_length=40)
    amount: Money | None = None
    currency: str | None = Field(None, pattern=r"^[A-Z]{3}$")


class Act(Actor, Version):
    pass


class DocumentUpdate(Act):
    title: Text = Field(max_length=200)
    body: Text = Field(max_length=10000)
    amount: Money | None = None
    currency: str | None = Field(None, pattern=r"^[A-Z]{3}$")


class RouteSelect(Act):
    route_id: Id = Field(alias="routeId")


class Decision(Act):
    step_id: Id | None = Field(None, alias="stepId")
    reason: str | None = Field(None, max_length=500)


class PostCreate(Actor):
    board_kind: Literal["NOTICE", "FREE"] = Field(alias="boardKind")
    title: Text = Field(max_length=200)
    body: Text = Field(max_length=10000)


class PostUpdate(Act):
    title: Text = Field(max_length=200)
    body: Text = Field(max_length=10000)


class AuthorityCreate(Model):
    code: Annotated[str, StringConstraints(pattern=r"^[A-Z0-9][A-Z0-9_-]{0,29}$")]
    document_kind: DocumentKind = Field(alias="documentKind")
    currency: str = Field("KRW", pattern=r"^[A-Z]{3}$")
    amount_from: Money = Field("0", alias="amountFrom")
    amount_to: Money | None = Field(None, alias="amountTo")
    final_seq: int = Field(alias="finalSeq", ge=1, le=3, strict=True)
    effective_from: Month = Field(alias="effectiveFrom")
    effective_to: Month | None = Field(None, alias="effectiveTo")
    is_active: bool = Field(True, alias="isActive", strict=True)


class AuthorityPatch(Version):
    code: Code | None = None
    document_kind: DocumentKind | None = Field(None, alias="documentKind")
    currency: str | None = Field(None, pattern=r"^[A-Z]{3}$")
    amount_from: Money | None = Field(None, alias="amountFrom")
    amount_to: Money | None = Field(None, alias="amountTo")
    final_seq: int | None = Field(None, alias="finalSeq", ge=1, le=3, strict=True)
    effective_from: Month | None = Field(None, alias="effectiveFrom")
    effective_to: Month | None = Field(None, alias="effectiveTo")
    is_active: bool | None = Field(None, alias="isActive", strict=True)


class DelegationCreate(Actor):
    delegate_person_id: Id = Field(alias="delegatePersonId")
    starts_at: AwareDatetime = Field(alias="startsAt")
    ends_at: AwareDatetime = Field(alias="endsAt")
    document_kind: DocumentKind | None = Field(None, alias="documentKind")
    max_amount: Money | None = Field(None, alias="maxAmount")
    reason: Text = Field(min_length=2, max_length=500)
