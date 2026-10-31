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
CALENDAR_CASES = {
    "CALENDAR_REMOVED_ATTENDEE": (404, "NOT_FOUND"),
    "CALENDAR_ATTENDEE_GUARD": (403, "GW_IDENTITY_REQUIRED"),
}
DELEGATION_CASES = {
    "DELEGATION_REVOKED": (404, "NOT_FOUND"),
    "DELEGATION_GUARD": (403, "GW_IDENTITY_REQUIRED"),
}
ALL_CASES = (
    CASES | OBJECT_CASES | POST_CASES | CHAT_CASES | CALENDAR_CASES | DELEGATION_CASES
)


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


class RestoredCalendarDenialObservation(RestoredDenialObservation):
    version: Literal[5]
    scope: Literal["SYNTHETIC_CLOSED_RESTORE_CALENDAR_AUTHORIZATION"]
    case: Literal["CALENDAR_REMOVED_ATTENDEE", "CALENDAR_ATTENDEE_GUARD"]
    source_comparison_scope: Literal[
        "SELECTED_AUTHORIZATION_CALENDAR_AND_RECEIPT_TABLES"
    ] = Field(alias="sourceComparisonScope")
    respond_status: int = Field(alias="respondStatus")
    respond_code: str = Field(alias="respondCode")
    replay_status: int = Field(alias="replayStatus")
    replay_code: str = Field(alias="replayCode")
    edit_status: int = Field(alias="editStatus")
    edit_code: str = Field(alias="editCode")
    cancel_status: int = Field(alias="cancelStatus")
    cancel_code: str = Field(alias="cancelCode")
    attendee_edit_status: int = Field(alias="attendeeEditStatus")
    attendee_edit_code: str = Field(alias="attendeeEditCode")
    attendee_cancel_status: int = Field(alias="attendeeCancelStatus")
    attendee_cancel_code: str = Field(alias="attendeeCancelCode")
    list_status: int = Field(alias="listStatus")
    list_code: str | None = Field(alias="listCode")
    listing_mode: Literal["FILTERED", "IDENTITY_DENIED"] = Field(alias="listingMode")
    baseline_read_confirmed: Literal[True] = Field(alias="baselineReadConfirmed")
    baseline_respond_confirmed: Literal[True] = Field(alias="baselineRespondConfirmed")
    baseline_owner_edit_confirmed: Literal[True] = Field(
        alias="baselineOwnerEditConfirmed"
    )
    restored_owner_read_confirmed: bool = Field(alias="restoredOwnerReadConfirmed")
    restored_owner_edit_confirmed: bool = Field(alias="restoredOwnerEditConfirmed")
    restored_attendee_read_confirmed: bool = Field(
        alias="restoredAttendeeReadConfirmed"
    )
    restored_attendee_respond_confirmed: bool = Field(
        alias="restoredAttendeeRespondConfirmed"
    )
    quarantine_observed: bool = Field(alias="quarantineObserved")
    company_hold: bool = Field(alias="companyHold")
    content_exposed: Literal[False] = Field(alias="contentExposed")
    denied_calendar_state_unchanged: Literal[True] = Field(
        alias="deniedCalendarStateUnchanged"
    )
    cached_receipt_retained: Literal[True] = Field(alias="cachedReceiptRetained")
    attendees_replayed: Literal[False] = Field(alias="attendeesReplayed")

    @model_validator(mode="before")
    @classmethod
    def exact_calendar_types(cls, value):
        if isinstance(value, dict):
            for key in (
                "baselineReadConfirmed",
                "baselineRespondConfirmed",
                "baselineOwnerEditConfirmed",
                "restoredOwnerReadConfirmed",
                "restoredOwnerEditConfirmed",
                "restoredAttendeeReadConfirmed",
                "restoredAttendeeRespondConfirmed",
                "quarantineObserved",
                "companyHold",
                "contentExposed",
                "deniedCalendarStateUnchanged",
                "cachedReceiptRetained",
                "attendeesReplayed",
            ):
                if type(value.get(key)) is not bool:
                    raise ValueError("exact calendar boolean required")
            for key in (
                "respondStatus",
                "replayStatus",
                "editStatus",
                "cancelStatus",
                "attendeeEditStatus",
                "attendeeCancelStatus",
                "listStatus",
            ):
                if type(value.get(key)) is not int:
                    raise ValueError("exact calendar status required")
        return value

    @model_validator(mode="after")
    def calendar_boundaries(self):
        expected = CALENDAR_CASES[self.case]
        if any(
            pair != expected
            for pair in (
                (self.respond_status, self.respond_code),
                (self.replay_status, self.replay_code),
                (self.edit_status, self.edit_code),
                (self.cancel_status, self.cancel_code),
                (self.attendee_edit_status, self.attendee_edit_code),
                (self.attendee_cancel_status, self.attendee_cancel_code),
            )
        ):
            raise ValueError("wrong calendar permission boundary")
        guarded = self.case == "CALENDAR_ATTENDEE_GUARD"
        if self.quarantine_observed != guarded or self.company_hold != guarded:
            raise ValueError("calendar quarantine mismatch")
        if any(
            v != (not guarded)
            for v in (
                self.restored_owner_read_confirmed,
                self.restored_owner_edit_confirmed,
                self.restored_attendee_read_confirmed,
                self.restored_attendee_respond_confirmed,
            )
        ):
            raise ValueError("calendar positive control mismatch")
        listing = (
            (403, "GW_IDENTITY_REQUIRED", "IDENTITY_DENIED")
            if guarded
            else (200, None, "FILTERED")
        )
        if (self.list_status, self.list_code, self.listing_mode) != listing:
            raise ValueError("wrong calendar listing boundary")
        return self


class RestoredDelegationDenialObservation(RestoredDenialObservation):
    version: Literal[6]
    scope: Literal["SYNTHETIC_CLOSED_RESTORE_DELEGATION_AUTHORIZATION"]
    case: Literal["DELEGATION_REVOKED", "DELEGATION_GUARD"]
    source_comparison_scope: Literal[
        "SELECTED_AUTHORIZATION_DELEGATION_DOCUMENT_AND_RECEIPT_TABLES"
    ] = Field(alias="sourceComparisonScope")
    approve_status: int = Field(alias="approveStatus")
    approve_code: str = Field(alias="approveCode")
    reject_status: int = Field(alias="rejectStatus")
    reject_code: str = Field(alias="rejectCode")
    list_status: int = Field(alias="listStatus")
    list_code: str | None = Field(alias="listCode")
    search_status: int = Field(alias="searchStatus")
    search_code: str | None = Field(alias="searchCode")
    history_status: int = Field(alias="historyStatus")
    history_code: str | None = Field(alias="historyCode")
    replay_status: int = Field(alias="replayStatus")
    replay_code: str | None = Field(alias="replayCode")
    listing_mode: Literal["FILTERED", "IDENTITY_DENIED"] = Field(alias="listingMode")
    baseline_delegated_read: Literal[True] = Field(alias="baselineDelegatedRead")
    baseline_delegated_approval: Literal[True] = Field(
        alias="baselineDelegatedApproval"
    )
    baseline_actor_history: Literal[True] = Field(alias="baselineActorHistory")
    restored_original_read: bool = Field(alias="restoredOriginalRead")
    restored_original_approval: bool = Field(alias="restoredOriginalApproval")
    restored_actor_history: bool = Field(alias="restoredActorHistory")
    quarantine_observed: bool = Field(alias="quarantineObserved")
    company_hold: bool = Field(alias="companyHold")
    content_exposed: Literal[False] = Field(alias="contentExposed")
    denied_delegation_state_unchanged: Literal[True] = Field(
        alias="deniedDelegationStateUnchanged"
    )
    restored_delegations_revoked: Literal[True] = Field(
        alias="restoredDelegationsRevoked"
    )
    cached_receipt_retained: Literal[True] = Field(alias="cachedReceiptRetained")
    delegation_replayed: Literal[False] = Field(alias="delegationReplayed")

    @model_validator(mode="before")
    @classmethod
    def exact_delegation_types(cls, value):
        if isinstance(value, dict):
            for key in (
                "baselineDelegatedRead",
                "baselineDelegatedApproval",
                "baselineActorHistory",
                "restoredOriginalRead",
                "restoredOriginalApproval",
                "restoredActorHistory",
                "quarantineObserved",
                "companyHold",
                "contentExposed",
                "restoredDelegationsRevoked",
                "deniedDelegationStateUnchanged",
                "cachedReceiptRetained",
                "delegationReplayed",
            ):
                if type(value.get(key)) is not bool:
                    raise ValueError("exact delegation boolean required")
            for key in (
                "approveStatus",
                "rejectStatus",
                "listStatus",
                "searchStatus",
                "historyStatus",
                "replayStatus",
            ):
                if type(value.get(key)) is not int:
                    raise ValueError("exact delegation status required")
        return value

    @model_validator(mode="after")
    def delegation_boundaries(self):
        expected = DELEGATION_CASES[self.case]
        if any(
            pair != expected
            for pair in (
                (self.approve_status, self.approve_code),
                (self.reject_status, self.reject_code),
            )
        ):
            raise ValueError("wrong current delegation boundary")
        guarded = self.case == "DELEGATION_GUARD"
        if self.quarantine_observed != guarded or self.company_hold != guarded:
            raise ValueError("delegation quarantine mismatch")
        if any(
            v != (not guarded)
            for v in (
                self.restored_original_read,
                self.restored_original_approval,
                self.restored_actor_history,
            )
        ):
            raise ValueError("delegation positive control mismatch")
        response = (403, "GW_IDENTITY_REQUIRED") if guarded else (200, None)
        if any(
            pair != response
            for pair in (
                (self.list_status, self.list_code),
                (self.search_status, self.search_code),
                (self.history_status, self.history_code),
                (self.replay_status, self.replay_code),
            )
        ) or self.listing_mode != ("IDENTITY_DENIED" if guarded else "FILTERED"):
            raise ValueError("delegation history/list boundary mismatch")
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
    if type(version) is not int or version not in {1, 2, 3, 4, 5, 6}:
        raise ValueError("unsupported restored denial version")
    model = {
        1: RestoredDenialObservation,
        2: RestoredObjectDenialObservation,
        3: RestoredPostDenialObservation,
        4: RestoredChatDenialObservation,
        5: RestoredCalendarDenialObservation,
        6: RestoredDelegationDenialObservation,
    }[version]
    return model.model_validate_json(raw, strict=True)
