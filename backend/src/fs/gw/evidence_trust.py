"""Server/operator-owned signer permissions, never capabilities supplied by proof files."""

import base64
import json
import os
import re
from collections.abc import Mapping
from types import MappingProxyType

from cryptography.exceptions import InvalidSignature

PURPOSES = frozenset(
    {
        "BACKUP",
        "RESTORE",
        "CHECKPOINT",
        "ACCEPTANCE_RECONCILIATION",
        "INCIDENT",
        "JOURNAL_OBSERVATION",
        "RESTORE_RECHECK",
        "CHECKPOINT_CATALOG",
    }
)


def purpose(kind):
    return {
        "BACKUP": "BACKUP",
        "RESTORE": "RESTORE",
        "CHECKPOINT": "CHECKPOINT",
        "CHECKPOINT_HEAD": "CHECKPOINT",
        "ACCEPTANCE": "ACCEPTANCE_RECONCILIATION",
        "INCIDENT": "INCIDENT",
        "JOURNAL_OBSERVATION": "JOURNAL_OBSERVATION",
        "RESTORE_RECHECK": "RESTORE_RECHECK",
        "CHECKPOINT_CATALOG": "CHECKPOINT_CATALOG",
    }.get(kind)


class EvidenceTrust(Mapping):
    def __init__(self, keys, scopes=None, *, catalog_lifecycle=None):
        self.catalog_lifecycle = catalog_lifecycle
        self._keys = MappingProxyType(dict(keys))
        self._scopes = None if scopes is None else MappingProxyType(dict(scopes))

    def __getitem__(self, key):
        return self._keys[key]

    def __iter__(self):
        return iter(self._keys)

    def __len__(self):
        return len(self._keys)

    @property
    def scopes(self):
        return self._scopes

    @property
    def scoped(self):
        return self._scopes is not None

    def authorize(self, key, use, workspace_id):
        if use == "CHECKPOINT_CATALOG" and self.catalog_lifecycle is not None:
            self.catalog_lifecycle.deny_current(key, workspace_id)
        if key not in self:
            raise ValueError("untrusted signer")
        if self._scopes is not None:
            companies, uses = self._scopes[key]
            if use not in uses or workspace_id not in companies:
                raise ValueError("signer scope mismatch")


def authorize(keys, key_id, kind, workspace_id):
    if isinstance(keys, EvidenceTrust):
        keys.authorize(key_id, purpose(kind), workspace_id)


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate configuration key")
        result[key] = value
    return result


def _json(value):
    if not isinstance(value, str) or len(value.encode()) > 65536:
        raise ValueError("invalid trust configuration")
    return json.loads(value, object_pairs_hook=_object)


def load(public_json, scopes_json=None, *, mode="PUBLIC_DEMO"):
    if mode not in {"PUBLIC_DEMO", "TEAM_TEST", "COMPANY"}:
        raise ValueError("unknown security mode")
    configured = _json(public_json)
    if not isinstance(configured, dict) or not 1 <= len(configured) <= 20:
        raise ValueError("invalid public keys")
    keys = {}
    for name, value in configured.items():
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,60}", name) or not isinstance(value, str):
            raise ValueError("invalid public key entry")
        raw = base64.b64decode(value, validate=True)
        if len(raw) != 32:
            raise ValueError("invalid public key size")
        keys[name] = raw
    if scopes_json is None:
        if mode == "COMPANY":
            raise ValueError("company signer scopes required")
        return EvidenceTrust(keys)
    document = _json(scopes_json)
    if (
        not isinstance(document, dict)
        or set(document) != {"version", "keys"}
        or type(document["version"]) is not int
        or document["version"] != 1
    ):
        raise ValueError("invalid scope version")
    records = document["keys"]
    if (
        not isinstance(records, dict)
        or set(records) != set(keys)
        or len(set(keys.values())) != len(keys)
    ):
        raise ValueError("missing scopes or aliased public key")
    scopes = {}
    for name, record in records.items():
        if not isinstance(record, dict) or set(record) != {"workspaceIds", "purposes"}:
            raise ValueError("invalid signer scope")
        companies, uses = record["workspaceIds"], record["purposes"]
        if (
            not isinstance(companies, list)
            or not 1 <= len(companies) <= 100
            or any(
                type(w) is not str
                or not re.fullmatch(r"[1-9][0-9]{0,18}", w)
                or int(w) > 9223372036854775807
                for w in companies
            )
            or len(set(companies)) != len(companies)
        ):
            raise ValueError("invalid company scopes")
        if (
            not isinstance(uses, list)
            or not uses
            or any(type(u) is not str or u not in PURPOSES for u in uses)
            or len(set(uses)) != len(uses)
        ):
            raise ValueError("invalid purpose scopes")
        if "ACCEPTANCE_RECONCILIATION" in uses and len(uses) != 1:
            raise ValueError("acceptance issuer must be separate")
        if "CHECKPOINT_CATALOG" in uses and len(uses) != 1:
            raise ValueError("checkpoint catalog authority must be separate")
        scopes[name] = (frozenset(companies), frozenset(uses))
    return EvidenceTrust(keys, scopes)


def configured_environment():
    """Validate proposed settings without accepting them against retained history.

    Only the explicit installation CLI may use this to propose a change.
    Readers must use from_environment(), which also checks retained history.
    """
    from fs.gw.trust_configuration import TrustConfigurationError

    try:
        trust = load(
            os.environ["FS_GW_EVIDENCE_PUBLIC_KEYS"],
            os.environ.get("FS_GW_EVIDENCE_KEY_SCOPES"),
            mode=os.environ.get("FS_SECURITY_MODE", "PUBLIC_DEMO"),
        )
    except OSError, ValueError, KeyError, TypeError, RecursionError:
        raise TrustConfigurationError("VERIFIER_CONFIGURATION") from None
    from fs.gw.catalog_key_handover import ENV, bind

    try:
        return bind(trust, os.environ[ENV]) if ENV in os.environ else trust
    except OSError, InvalidSignature, RecursionError, ValueError, KeyError, TypeError:
        raise TrustConfigurationError("CATALOG_LIFECYCLE") from None


def from_environment():
    from fs.gw import catalog_trust_store as floor
    from fs.gw.trust_configuration import TrustConfigurationError

    trust = configured_environment()
    if not floor.required(trust) and floor.ENV not in os.environ:
        return trust
    if floor.ENV not in os.environ:
        raise TrustConfigurationError("TRUST_STORE_REQUIRED")
    try:
        return floor.check(trust, os.environ[floor.ENV])
    except TrustConfigurationError:
        raise
    except OSError, InvalidSignature, RecursionError, ValueError, KeyError, TypeError:
        raise TrustConfigurationError("TRUST_STORE_UNAVAILABLE") from None
