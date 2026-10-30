"""Fixed synthetic restored-authentication checks; not live revocation acceptance."""

from typing import Literal

from pydantic import Field, model_validator

from fs.gw.operating_contract import StrictModel, timestamp

PROPERTY = "gwRestoredDenial"
CASES = {
    "CORE_ACCOUNT": (401, "INVALID_CREDENTIALS"),
    "COMPANY_MEMBERSHIP": (403, "COMPANY_ACCESS_DENIED"),
    "GW_BINDING": (403, "GW_IDENTITY_REQUIRED"),
    "GW_ROLE": (403, "GW_ROLE_REQUIRED"),
    "HR_AUTHORITY": (403, "WORK_ACCESS_DENIED"),
}


OBJECT_CASES = {
    "DOCUMENT_READER": (404, "NOT_FOUND"),
    "FOREIGN_SCOPE": (403, "COMPANY_ACCESS_DENIED"),
}
ALL_CASES = CASES | OBJECT_CASES


class RestoredDenialObservation(StrictModel):
    version: Literal[1]
    scope: Literal["SYNTHETIC_CLOSED_RESTORE_AUTHENTICATION"]
    case: Literal[
        "CORE_ACCOUNT", "COMPANY_MEMBERSHIP", "GW_BINDING", "GW_ROLE", "HR_AUTHORITY"
    ]
    run_id: str = Field(alias="runId", pattern=r"^[0-9a-f-]{36}$")
    code_revision: str = Field(alias="codeRevision", pattern=r"^[0-9a-f]{7,64}$")
    db_revision: str = Field(alias="dbRevision", pattern=r"^[A-Za-z0-9_]{1,100}$")
    started_at: str = Field(alias="startedAt")
    finished_at: str = Field(alias="finishedAt")
    # Digests bind actual signed restore bytes, never target URLs or credentials.
    restore_digest: str = Field(alias="restoreDigest", pattern=r"^[0-9a-f]{64}$")
    status: int
    error_code: str = Field(alias="errorCode")
    control_mfa_authenticated: Literal[True] = Field(alias="controlMfaAuthenticated")
    subject_mfa_authenticated: bool = Field(alias="subjectMfaAuthenticated")
    closed_before: Literal[True] = Field(alias="closedBefore")
    closed_after: Literal[True] = Field(alias="closedAfter")
    source_comparison_scope: Literal["SELECTED_AUTHORIZATION_TABLES"] = Field(
        alias="sourceComparisonScope"
    )
    source_unchanged: Literal[True] = Field(alias="sourceUnchanged")
    ready: Literal[False]
    revocations_complete: Literal[False] = Field(alias="revocationsComplete")
    live_company_acceptance: Literal[False] = Field(alias="liveCompanyAcceptance")

    @model_validator(mode="before")
    @classmethod
    def exact_types(cls, value):
        if isinstance(value, dict):
            for name in (
                "controlMfaAuthenticated",
                "subjectMfaAuthenticated",
                "closedBefore",
                "closedAfter",
                "sourceUnchanged",
                "ready",
                "revocationsComplete",
                "liveCompanyAcceptance",
            ):
                if type(value.get(name)) is not bool:
                    raise ValueError("exact boolean required")
            if (
                type(value.get("version")) is not int
                or type(value.get("status")) is not int
            ):
                raise ValueError("exact integer required")
        return value

    @model_validator(mode="after")
    def measured_denial(self):
        from uuid import UUID

        if str(UUID(self.run_id)) != self.run_id or UUID(self.run_id).version != 4:
            raise ValueError("run must be UUID4")
        if (self.status, self.error_code) != ALL_CASES[self.case]:
            raise ValueError("wrong denial boundary")
        if self.subject_mfa_authenticated != (self.case != "CORE_ACCOUNT"):
            raise ValueError("authentication boundary mismatch")
        if timestamp(self.started_at) > timestamp(self.finished_at):
            raise ValueError("observation time mismatch")
        return self


class RestoredObjectDenialObservation(RestoredDenialObservation):
    version: Literal[2]
    scope: Literal["SYNTHETIC_CLOSED_RESTORE_OBJECT_AUTHORIZATION"]
    case: Literal["DOCUMENT_READER", "FOREIGN_SCOPE"]
    source_comparison_scope: Literal["SELECTED_AUTHORIZATION_AND_DOCUMENT_TABLES"] = (
        Field(alias="sourceComparisonScope")
    )
    write_status: int = Field(alias="writeStatus")
    write_error_code: str = Field(alias="writeErrorCode")
    positive_object_read: Literal[True] = Field(alias="positiveObjectRead")
    positive_object_write: Literal[True] = Field(alias="positiveObjectWrite")
    list_hidden: Literal[True] = Field(alias="listHidden")
    denied_object_state_unchanged: Literal[True] = Field(
        alias="deniedObjectStateUnchanged"
    )
    hidden_scope_read_status: int | None = Field(None, alias="hiddenScopeReadStatus")
    hidden_scope_write_status: int | None = Field(None, alias="hiddenScopeWriteStatus")
    hidden_scope_read_code: str | None = Field(None, alias="hiddenScopeReadCode")
    hidden_scope_write_code: str | None = Field(None, alias="hiddenScopeWriteCode")

    @model_validator(mode="before")
    @classmethod
    def exact_object_types(cls, value):
        if isinstance(value, dict):
            for name in (
                "positiveObjectRead",
                "positiveObjectWrite",
                "listHidden",
                "deniedObjectStateUnchanged",
            ):
                if type(value.get(name)) is not bool:
                    raise ValueError("exact object boolean required")
            for name in (
                "writeStatus",
                "hiddenScopeReadStatus",
                "hiddenScopeWriteStatus",
            ):
                if value.get(name) is not None and type(value[name]) is not int:
                    raise ValueError("exact object status required")
        return value

    @model_validator(mode="after")
    def object_boundaries(self):
        if (self.write_status, self.write_error_code) != OBJECT_CASES[self.case]:
            raise ValueError("wrong object write boundary")
        hidden = (
            self.hidden_scope_read_status,
            self.hidden_scope_write_status,
            self.hidden_scope_read_code,
            self.hidden_scope_write_code,
        )
        expected = (
            (404, 404, "NOT_FOUND", "NOT_FOUND")
            if self.case == "FOREIGN_SCOPE"
            else (None, None, None, None)
        )
        if hidden != expected:
            raise ValueError("wrong hidden scope boundary")
        return self


def parse_observation(raw):
    import json

    if not isinstance(raw, str) or len(raw.encode()) > 8192:
        raise ValueError("invalid observation size")

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate observation key")
            result[key] = value
        return result

    payload = json.loads(raw, object_pairs_hook=unique)
    version = payload.get("version") if isinstance(payload, dict) else None
    if type(version) is not int or version not in {1, 2}:
        raise ValueError("unsupported restored denial version")
    model = (
        RestoredDenialObservation if version == 1 else RestoredObjectDenialObservation
    )
    return model.model_validate_json(raw, strict=True)
