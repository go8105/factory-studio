"""Fixed synthetic probe references shared by runner and unexecuted review map."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import get_args

from fs.gw.restored_denial import (
    CALENDAR_CASES,
    CASES,
    CHAT_CASES,
    DELEGATION_BOUND_CASES,
    DELEGATION_CASES,
    DELEGATION_RELATION_CASES,
    OBJECT_CASES,
    POST_CASES,
    STORED_DELEGATION_CASES,
    RestoredCalendarDenialObservation,
    RestoredChatDenialObservation,
    RestoredDelegationBoundaryObservation,
    RestoredDelegationDenialObservation,
    RestoredDelegationRelationObservation,
    RestoredDenialObservation,
    RestoredObjectDenialObservation,
    RestoredPostDenialObservation,
    StoredDelegationRuntimeObservation,
)

CATALOG_VERSION = "GW_RESTORED_DENIAL_PROBES_V9"


@dataclass(frozen=True)
class ProbeFamily:
    cases: tuple[str, ...]
    filename: str
    function: str
    observation: type[RestoredDenialObservation]

    @property
    def observation_version(self):
        return get_args(self.observation.model_fields["version"].annotation)[0]

    @property
    def observation_scope(self):
        return get_args(self.observation.model_fields["scope"].annotation)[0]

    def reference(self, case):
        return ("backend/tests/" + self.filename, self.function + "[" + case + "]")


FAMILIES = (
    ProbeFamily(
        tuple(CASES),
        "test_gw_restored_denial_db.py",
        "test_closed_restore_fresh_authentication_denial",
        RestoredDenialObservation,
    ),
    ProbeFamily(
        tuple(OBJECT_CASES),
        "test_gw_restored_object_db.py",
        "test_closed_restore_object_authorization",
        RestoredObjectDenialObservation,
    ),
    ProbeFamily(
        tuple(POST_CASES),
        "test_gw_restored_post_db.py",
        "test_closed_restore_post_visibility",
        RestoredPostDenialObservation,
    ),
    ProbeFamily(
        tuple(CHAT_CASES),
        "test_gw_restored_chat_db.py",
        "test_closed_restore_chat_membership",
        RestoredChatDenialObservation,
    ),
    ProbeFamily(
        tuple(CALENDAR_CASES),
        "test_gw_restored_calendar_db.py",
        "test_closed_restore_calendar_authorization",
        RestoredCalendarDenialObservation,
    ),
    ProbeFamily(
        tuple(DELEGATION_CASES),
        "test_gw_restored_delegation_db.py",
        "test_closed_restore_delegation_authorization",
        RestoredDelegationDenialObservation,
    ),
    ProbeFamily(
        tuple(DELEGATION_BOUND_CASES),
        "test_gw_restored_delegation_bounds_db.py",
        "test_source_bounds_and_restored_delegation_floor",
        RestoredDelegationBoundaryObservation,
    ),
    ProbeFamily(
        tuple(DELEGATION_RELATION_CASES),
        "test_gw_restored_delegation_relations_db.py",
        "test_source_relation_money_and_restored_floor",
        RestoredDelegationRelationObservation,
    ),
    ProbeFamily(
        tuple(STORED_DELEGATION_CASES),
        "test_gw_stored_delegation_runtime_db.py",
        "test_stored_delegation_policy_acl_and_restore",
        StoredDelegationRuntimeObservation,
    ),
)

DENIAL_PROBES = MappingProxyType(
    {
        "RESTORED_FRESH_AUTH_" + case: family.reference(case)
        for family in FAMILIES
        for case in family.cases
    }
)


def review_cases(cases):
    """Metadata only: no DB/file/process reads and no imported execution results."""
    selected = frozenset(cases)
    known = {case for family in FAMILIES for case in family.cases}
    if not selected <= known:
        raise ValueError("unknown fixed synthetic case")
    return [
        {
            "case": case,
            "probe": "RESTORED_FRESH_AUTH_" + case,
            "testReference": "::".join(family.reference(case)),
            "observationVersion": family.observation_version,
            "observationScope": family.observation_scope,
            "executionState": "NOT_EXECUTED",
            "currentCompanyVerified": False,
        }
        for family in FAMILIES
        for case in family.cases
        if case in selected
    ]
