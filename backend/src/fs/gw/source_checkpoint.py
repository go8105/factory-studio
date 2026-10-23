"""Private snapshot comparison for fields actually captured by restore checkpoints.

No raw accounts, credentials or snapshots belong in the signed public summary.
This compares two instants; it cannot prove collection completeness or history.
"""

import hashlib
from typing import Literal

from pydantic import Field, model_validator

from fs.gw.operating_contract import StrictModel, canonical, timestamp


def normalized(value):
    if isinstance(value, dict):
        return {key: normalized(item) for key, item in value.items()}
    if isinstance(value, list):
        return sorted((normalized(item) for item in value), key=canonical)
    return value


def state_digest(value):
    return hashlib.sha256(canonical(normalized(value))).hexdigest()


def changed_groups(saved, current):
    return {
        "core": sum(
            state_digest(saved["core"].get(key))
            != state_digest(current["core"].get(key))
            for key in saved["core"].keys() | current["core"].keys()
        ),
        "gw": sum(
            state_digest(saved["gw"].get(key)) != state_digest(current["gw"].get(key))
            for key in saved["gw"].keys() | current["gw"].keys()
        ),
        "hr": int(state_digest(saved["hr"]) != state_digest(current["hr"])),
    }


class ChangedGroups(StrictModel):
    core: int = Field(ge=0, le=100)
    gw: int = Field(ge=0, le=100)
    hr: int = Field(ge=0, le=1)


class SourceCheckpointObservation(StrictModel):
    version: Literal[1]
    scope: Literal["CURRENT_SOURCE_CHECKPOINT_FIELDS"]
    observed_at: str = Field(alias="observedAt")
    source_identity: str = Field(alias="sourceIdentity", pattern=r"^[0-9a-f]{64}$")
    checkpoint_state_digest: str = Field(
        alias="checkpointStateDigest", pattern=r"^[0-9a-f]{64}$"
    )
    current_state_digest: str | None = Field(
        alias="currentStateDigest", pattern=r"^[0-9a-f]{64}$"
    )
    source_measured: bool = Field(alias="sourceMeasured")
    context_matches: bool | None = Field(alias="contextMatches")
    changed_groups: ChangedGroups | None = Field(alias="changedGroups")
    reason: Literal["MATCH", "CHANGED", "MEASUREMENT_UNAVAILABLE"]
    result: Literal["PARTIAL", "BLOCKED"]

    @model_validator(mode="before")
    @classmethod
    def integer_version(cls, value):
        if isinstance(value, dict) and type(value.get("version")) is not int:
            raise ValueError("invalid source observation version")
        return value

    @model_validator(mode="after")
    def consistent(self):
        timestamp(self.observed_at)
        if not self.source_measured:
            if (
                self.current_state_digest is not None
                or self.context_matches is not None
                or self.changed_groups is not None
                or self.reason != "MEASUREMENT_UNAVAILABLE"
                or self.result != "BLOCKED"
            ):
                raise ValueError("source measurements cannot be inferred")
        else:
            if (
                self.current_state_digest is None
                or self.context_matches is None
                or self.changed_groups is None
            ):
                raise ValueError("source measurements required")
            same = self.current_state_digest == self.checkpoint_state_digest
            if same != (not any(self.changed_groups.model_dump().values())):
                raise ValueError("source digest and change groups mismatch")
            matches = same and self.context_matches
            if self.reason != ("MATCH" if matches else "CHANGED") or self.result != (
                "PARTIAL" if matches else "BLOCKED"
            ):
                raise ValueError("source comparison result mismatch")
        return self
