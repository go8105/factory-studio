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
        if (self.status, self.error_code) != CASES[self.case]:
            raise ValueError("wrong denial boundary")
        if self.subject_mfa_authenticated != (self.case != "CORE_ACCOUNT"):
            raise ValueError("authentication boundary mismatch")
        if timestamp(self.started_at) > timestamp(self.finished_at):
            raise ValueError("observation time mismatch")
        return self
