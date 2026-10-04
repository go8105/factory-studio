"""FS-030 strict request contracts. IDs accept decimal strings; money stays decimal text."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

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


class Step(Model):
    person_id: Id = Field(alias="personId")


class RouteCreate(Model):
    code: Code
    name: Text = Field(max_length=100)
    steps: list[Step] = Field(min_length=1, max_length=3)


class RouteUpdate(Version):
    name: Text = Field(max_length=100)
    is_active: bool = Field(alias="isActive", strict=True)
    steps: list[Step] = Field(min_length=1, max_length=3)


class DocumentCreate(Actor):
    title: Text = Field(max_length=200)
    body: Text = Field(max_length=10000)
    route_id: Id = Field(alias="routeId")
    kind: Literal["GENERAL", "ERP_PURCHASE"]
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
    reason: str | None = Field(None, max_length=500)


class PostCreate(Actor):
    board_kind: Literal["NOTICE", "FREE"] = Field(alias="boardKind")
    title: Text = Field(max_length=200)
    body: Text = Field(max_length=10000)


class PostUpdate(Act):
    title: Text = Field(max_length=200)
    body: Text = Field(max_length=10000)
