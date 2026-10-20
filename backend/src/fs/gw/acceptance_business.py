"""Bounded synthetic execution observation; never live acceptance evidence."""

from typing import Literal, get_args

from pydantic import Field, model_validator

from fs.gw.operating_contract import EvidenceReference, StrictModel, timestamp

PROPERTY = "gwSyntheticBusiness"
PROBE = "TEN_PERSON_MFA_AND_REPRESENTATIVE_BUSINESS"


class SyntheticBusinessObservation(StrictModel):
    version: Literal[1]
    scope: Literal["SYNTHETIC_TEN_PERSON_ASGI"]
    run_id: str = Field(alias="runId")
    context_digest: str = Field(alias="contextDigest", pattern=r"^[0-9a-f]{64}$")
    final_context_digest: str = Field(
        alias="finalContextDigest", pattern=r"^[0-9a-f]{64}$"
    )
    policy_digest: str = Field(alias="policyDigest", pattern=r"^[0-9a-f]{64}$")
    workspace_id: str = Field(alias="workspaceId", pattern=r"^[1-9][0-9]{0,18}$")
    generation_id: str = Field(alias="generationId", pattern=r"^[1-9][0-9]{0,18}$")
    code_revision: str = Field(alias="codeRevision", pattern=r"^[0-9a-f]{7,64}$")
    db_revision: str = Field(alias="dbRevision", pattern=r"^[A-Za-z0-9_]{1,100}$")
    started_at: str = Field(alias="startedAt")
    finished_at: str = Field(alias="finishedAt")
    preflight_result: Literal["PARTIAL"] = Field(alias="preflightResult")
    final_preflight_result: Literal["PARTIAL"] = Field(alias="finalPreflightResult")
    mfa_authenticated: Literal[10] = Field(alias="mfaAuthenticated")
    security_administrators: Literal[1] = Field(alias="securityAdministrators")
    staff: Literal[9]
    approved_documents: Literal[9] = Field(alias="approvedDocuments")
    published_posts: Literal[9] = Field(alias="publishedPosts")
    accepted_attendees: Literal[9] = Field(alias="acceptedAttendees")
    comments: Literal[9]
    notifications_read: Literal[9] = Field(alias="notificationsRead")
    messages: Literal[10]
    denied_staff_admin_reads: Literal[9] = Field(alias="deniedStaffAdminReads")
    denied_other_draft_reads: Literal[9] = Field(alias="deniedOtherDraftReads")
    ready: Literal[False]
    live_company_acceptance: Literal[False] = Field(alias="liveCompanyAcceptance")
    device_checks: Literal["UNVERIFIED"] = Field(alias="deviceChecks")
    network_checks: Literal["UNVERIFIED"] = Field(alias="networkChecks")
    representative_live_business: Literal["UNVERIFIED"] = Field(
        alias="representativeLiveBusiness"
    )

    @model_validator(mode="before")
    @classmethod
    def exact_json_types(cls, value):
        if isinstance(value, dict):
            for name, field in cls.model_fields.items():
                key = field.alias if field.alias in value else name
                args = get_args(field.annotation)
                expected = args[0] if args else None
                if (
                    type(expected) in {int, bool}
                    and key in value
                    and type(value[key]) is not type(expected)
                ):
                    raise ValueError("측정 수와 미확인 표지의 JSON 형식을 확인하세요.")
        return value

    @model_validator(mode="after")
    def bound_run(self):
        EvidenceReference(runId=self.run_id, sourceDigest=self.context_digest)
        if self.context_digest != self.final_context_digest:
            raise ValueError("실행 중 현재 인수 기준이 달라졌습니다.")
        if timestamp(self.finished_at) < timestamp(self.started_at):
            raise ValueError("실행 시각 순서를 확인하세요.")
        return self
