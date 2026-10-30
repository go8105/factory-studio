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
POST_CASES = {
    "POST_ORG_SCOPE": (404, "NOT_FOUND"),
    "POST_VISIBILITY_GUARD": (403, "GW_IDENTITY_REQUIRED"),
}
CHAT_CASES = {
    "CHAT_LEFT_MEMBER": (404, "NOT_FOUND"),
    "CHAT_MEMBERSHIP_GUARD": (403, "GW_IDENTITY_REQUIRED"),
}
ALL_CASES = CASES | OBJECT_CASES | POST_CASES | CHAT_CASES


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


class RestoredPostDenialObservation(RestoredDenialObservation):
    version: Literal[3]
    scope: Literal["SYNTHETIC_CLOSED_RESTORE_POST_VISIBILITY"]
    case: Literal["POST_ORG_SCOPE", "POST_VISIBILITY_GUARD"]
    source_comparison_scope: Literal[
        "SELECTED_AUTHORIZATION_ORGANIZATION_AND_POST_TABLES"
    ] = Field(alias="sourceComparisonScope")
    write_status: int = Field(alias="writeStatus")
    write_error_code: str = Field(alias="writeErrorCode")
    baseline_read_confirmed: Literal[True] = Field(alias="baselineReadConfirmed")
    baseline_write_confirmed: Literal[True] = Field(alias="baselineWriteConfirmed")
    restored_owner_read_confirmed: bool = Field(alias="restoredOwnerReadConfirmed")
    restored_public_read_confirmed: bool = Field(alias="restoredPublicReadConfirmed")
    restored_org_read_confirmed: bool = Field(alias="restoredOrgReadConfirmed")
    restored_own_draft_write_confirmed: bool = Field(
        alias="restoredOwnDraftWriteConfirmed"
    )
    quarantine_observed: bool = Field(alias="quarantineObserved")
    company_hold: bool = Field(alias="companyHold")
    content_exposed: Literal[False] = Field(alias="contentExposed")
    denied_post_state_unchanged: Literal[True] = Field(alias="deniedPostStateUnchanged")
    listing_mode: Literal["FILTERED", "IDENTITY_DENIED"] = Field(alias="listingMode")
    list_status: int = Field(alias="listStatus")
    search_status: int = Field(alias="searchStatus")
    list_code: str | None = Field(alias="listCode")
    search_code: str | None = Field(alias="searchCode")
    visibility_replayed: Literal[False] = Field(alias="visibilityReplayed")

    @model_validator(mode="before")
    @classmethod
    def exact_post_types(cls, value):
        if isinstance(value, dict):
            for key in (
                "baselineReadConfirmed",
                "baselineWriteConfirmed",
                "restoredOwnerReadConfirmed",
                "restoredPublicReadConfirmed",
                "restoredOrgReadConfirmed",
                "restoredOwnDraftWriteConfirmed",
                "quarantineObserved",
                "companyHold",
                "contentExposed",
                "deniedPostStateUnchanged",
                "visibilityReplayed",
            ):
                if type(value.get(key)) is not bool:
                    raise ValueError("exact post boolean required")
            for key in ("writeStatus", "listStatus", "searchStatus"):
                if type(value.get(key)) is not int:
                    raise ValueError("exact post status required")
        return value

    @model_validator(mode="after")
    def post_boundaries(self):
        guarded = self.case == "POST_VISIBILITY_GUARD"
        if (self.write_status, self.write_error_code) != POST_CASES[self.case]:
            raise ValueError("wrong post write boundary")
        if self.quarantine_observed != guarded or self.company_hold != guarded:
            raise ValueError("post quarantine mismatch")
        if any(
            v != (not guarded)
            for v in (
                self.restored_owner_read_confirmed,
                self.restored_public_read_confirmed,
                self.restored_org_read_confirmed,
                self.restored_own_draft_write_confirmed,
            )
        ):
            raise ValueError("post positive control mismatch")
        expected = (
            (
                403,
                403,
                "GW_IDENTITY_REQUIRED",
                "GW_IDENTITY_REQUIRED",
                "IDENTITY_DENIED",
            )
            if guarded
            else (200, 200, None, None, "FILTERED")
        )
        if (
            self.list_status,
            self.search_status,
            self.list_code,
            self.search_code,
            self.listing_mode,
        ) != expected:
            raise ValueError("post list boundary mismatch")
        return self


class RestoredChatDenialObservation(RestoredDenialObservation):
    version: Literal[4]
    scope: Literal["SYNTHETIC_CLOSED_RESTORE_CHAT_MEMBERSHIP"]
    case: Literal["CHAT_LEFT_MEMBER", "CHAT_MEMBERSHIP_GUARD"]
    source_comparison_scope: Literal[
        "SELECTED_AUTHORIZATION_CHAT_AND_RECEIPT_TABLES"
    ] = Field(alias="sourceComparisonScope")
    write_status: int = Field(alias="writeStatus")
    write_error_code: str = Field(alias="writeErrorCode")
    replay_status: int = Field(alias="replayStatus")
    replay_code: str = Field(alias="replayCode")
    cursor_status: int = Field(alias="cursorStatus")
    cursor_code: str = Field(alias="cursorCode")
    read_status: int = Field(alias="readStatus")
    read_code: str = Field(alias="readCode")
    list_status: int = Field(alias="listStatus")
    list_code: str | None = Field(alias="listCode")
    listing_mode: Literal["FILTERED", "IDENTITY_DENIED"] = Field(alias="listingMode")
    baseline_read_confirmed: Literal[True] = Field(alias="baselineReadConfirmed")
    baseline_send_confirmed: Literal[True] = Field(alias="baselineSendConfirmed")
    baseline_cursor_confirmed: Literal[True] = Field(alias="baselineCursorConfirmed")
    restored_owner_read_confirmed: bool = Field(alias="restoredOwnerReadConfirmed")
    restored_shared_read_confirmed: bool = Field(alias="restoredSharedReadConfirmed")
    restored_shared_send_confirmed: bool = Field(alias="restoredSharedSendConfirmed")
    restored_shared_cursor_confirmed: bool = Field(
        alias="restoredSharedCursorConfirmed"
    )
    quarantine_observed: bool = Field(alias="quarantineObserved")
    company_hold: bool = Field(alias="companyHold")
    content_exposed: Literal[False] = Field(alias="contentExposed")
    denied_chat_state_unchanged: Literal[True] = Field(alias="deniedChatStateUnchanged")
    cached_receipt_retained: Literal[True] = Field(alias="cachedReceiptRetained")
    membership_replayed: Literal[False] = Field(alias="membershipReplayed")

    @model_validator(mode="before")
    @classmethod
    def exact_chat_types(cls, value):
        if isinstance(value, dict):
            for key in (
                "baselineReadConfirmed",
                "baselineSendConfirmed",
                "baselineCursorConfirmed",
                "restoredOwnerReadConfirmed",
                "restoredSharedReadConfirmed",
                "restoredSharedSendConfirmed",
                "restoredSharedCursorConfirmed",
                "quarantineObserved",
                "companyHold",
                "contentExposed",
                "deniedChatStateUnchanged",
                "membershipReplayed",
                "cachedReceiptRetained",
            ):
                if type(value.get(key)) is not bool:
                    raise ValueError("exact chat boolean required")
            for key in (
                "writeStatus",
                "replayStatus",
                "cursorStatus",
                "readStatus",
                "listStatus",
            ):
                if type(value.get(key)) is not int:
                    raise ValueError("exact chat status required")
        return value

    @model_validator(mode="after")
    def chat_boundaries(self):
        expected = CHAT_CASES[self.case]
        if any(
            pair != expected
            for pair in (
                (self.write_status, self.write_error_code),
                (self.replay_status, self.replay_code),
                (self.cursor_status, self.cursor_code),
                (self.read_status, self.read_code),
            )
        ):
            raise ValueError("wrong chat permission boundary")
        guarded = self.case == "CHAT_MEMBERSHIP_GUARD"
        if self.quarantine_observed != guarded or self.company_hold != guarded:
            raise ValueError("chat quarantine mismatch")
        if any(
            v != (not guarded)
            for v in (
                self.restored_owner_read_confirmed,
                self.restored_shared_read_confirmed,
                self.restored_shared_send_confirmed,
                self.restored_shared_cursor_confirmed,
            )
        ):
            raise ValueError("chat positive control mismatch")
        listing = (
            (403, "GW_IDENTITY_REQUIRED", "IDENTITY_DENIED")
            if guarded
            else (200, None, "FILTERED")
        )
        if (self.list_status, self.list_code, self.listing_mode) != listing:
            raise ValueError("wrong chat listing boundary")
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
    if type(version) is not int or version not in {1, 2, 3, 4}:
        raise ValueError("unsupported restored denial version")
    model = {
        1: RestoredDenialObservation,
        2: RestoredObjectDenialObservation,
        3: RestoredPostDenialObservation,
        4: RestoredChatDenialObservation,
    }[version]
    return model.model_validate_json(raw, strict=True)
