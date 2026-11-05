"""Repeated catalog rotation without older private keys preserves exact history and revocation."""

# ruff: noqa: F401,F811
import base64
import json
from copy import deepcopy
from datetime import timedelta

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fs.gw import catalog_key_chain as chain
from fs.gw import catalog_key_handover as handover
from fs.gw import catalog_store as store
from fs.gw.evidence_trust import EvidenceTrust
from fs.gw.operating_contract import canonical
from test_gw_catalog_key_handover import source
from test_gw_catalog_segments import finish, package
from test_gw_catalog_store import setup
from test_gw_catalog_transfer import outgoing, receive, receiver


class Rotations:
    def __init__(self, parts, patch, kind="PARTIAL"):
        self.parts = parts
        self.current = source(parts, patch, kind)
        self.active = "catalog"
        self.private = {"catalog": parts[1]["signer"]}
        self.public = dict(parts[1]["public_keys"])
        self.scopes = dict(parts[1]["public_keys"].scopes)
        self.config = {"version": 1, "keys": []}
        self.number = 0
        self.root_receipts = {}
        self.prepared = None

    def save(self, raw):
        self.number += 1
        path = self.parts[0].parent / f"chain-{self.number}.json"
        path.write_bytes(raw)
        path.chmod(0o600)
        return {"version": 1, "file": str(path), "digest": store.digest(raw)}

    def keys(self, config=None):
        keys = EvidenceTrust(self.public, self.scopes)
        config = self.config if config is None else config
        return handover.bind(keys, json.dumps(config)) if config["keys"] else keys

    def prepare(self, next_id):
        successor = Ed25519PrivateKey.generate()
        self.private[next_id] = successor
        self.public[next_id] = successor.public_key().public_bytes_raw()
        self.scopes[next_id] = (
            frozenset([str(self.parts[2]["workspace_id"])]),
            frozenset(["CHECKPOINT_CATALOG"]),
        )
        keys = self.keys()
        kw = {
            "context": self.parts[1]["context"],
            "public_keys": keys,
            "retiring_signer": self.private[self.active],
            "retiring_id": self.active,
            "successor_signer": successor,
            "successor_id": next_id,
            "expected_pin_digest": self.current["pinDigest"],
            "now": self.parts[1]["now"],
        }
        raw, _ = handover.issue(self.parts[0], **kw)
        approval = self.save(raw)
        self.root_receipts[self.active] = approval
        self.prepared = next_id, kw, approval
        return kw, approval

    def extension(self, record, **changes):
        from pathlib import Path

        _, kw, own = self.prepared
        parent = record["approvals"][0]
        args = {
            "parent_raw": Path(parent["file"]).read_bytes(),
            "retiring_handover_raw": Path(own["file"]).read_bytes(),
            "predecessor_id": record["keyId"],
            "expected_parent_digest": parent["digest"],
            "expected_retiring_handover_digest": own["digest"],
        } | kw
        args.update(changes)
        return chain.extend(self.parts[0], **args)

    def commit(self):
        next_id, kw, approval = self.prepared
        updated = deepcopy(self.config)
        for record in updated["keys"]:
            raw, _ = self.extension(record)
            record["approvals"] = [self.save(raw)]
        updated["keys"].append(
            {
                "version": 1,
                "workspaceId": str(self.parts[2]["workspace_id"]),
                "keyId": self.active,
                "publicKey": base64.b64encode(self.public[self.active]).decode(),
                "state": "RETIRED",
                "approvals": [approval],
            }
        )
        self.current = store.publish(
            self.parts[0],
            context=kw["context"],
            public_keys=kw["public_keys"],
            signer=kw["successor_signer"],
            signer_id=next_id,
            now=kw["now"],
            expected_pin_digest=self.current["pinDigest"],
            operation="refresh",
        )
        self.public.pop(self.active)
        self.scopes.pop(self.active)
        self.private.pop(
            self.active
        )  # Older private keys are unavailable to every later operation.
        self.parts[1]["signer"] = None
        self.config, self.active = updated, next_id
        keys = self.keys()
        self.parts[1]["public_keys"] = self.parts[2]["public_keys"] = keys
        self.prepared = None
        return keys

    def rotate(self, next_id):
        self.prepare(next_id)
        return self.commit()


@pytest.mark.parametrize("kind", ["PASS", "FAIL", "PARTIAL"])
@pytest.mark.parametrize("transport", ["single", "segments"])
@pytest.mark.parametrize("existing", [False, True])
def test_three_rotations_only_latest_private_key_and_exact_old_history(
    setup, monkeypatch, kind, transport, existing
):
    rotations = Rotations(setup, monkeypatch, kind)
    dest = receiver(setup)
    old = receive(setup, dest, *outgoing(setup)) if existing else None
    base = rotations.current
    originals = {p.name: p.read_bytes() for p in setup[0].glob("catalog-*.json")}
    for identity in ["catalog-b", "catalog-c", "catalog-d"]:
        keys = rotations.rotate(identity)
        current, _ = store.managed_read(
            setup[0] / store.PIN,
            public_keys=keys,
            workspace_id=setup[2]["workspace_id"],
            now=setup[1]["now"],
        )
        assert current.records[0].result == kind and current.signer_key_id == identity
    assert set(rotations.private) == {"catalog-d"} and setup[1]["signer"] is None
    revision, sha = (base["revision"], base["catalogDigest"]) if old else (0, "ABSENT")
    if transport == "single":
        result = receive(setup, dest, *outgoing(setup, revision, sha), old)
    else:
        result = finish(
            setup,
            dest,
            package(setup, revision, sha),
            old,
            **({"resume": False} if old else {}),
        )
    assert (
        result["result"] == kind
        and result["revision"] == rotations.current["revision"]
        and not result["ready"]
    )
    assert all(
        (setup[0] / name).read_bytes() == data for name, data in originals.items()
    )
    if not existing:
        assert all(
            (dest / name).read_bytes() == data for name, data in originals.items()
        )


@pytest.mark.parametrize(
    "problem",
    [
        "root_revoked",
        "intermediate_revoked",
        "missing_intermediate",
        "old_root_replay",
        "missing_own_root",
        "wrong_own_root",
        "endpoint_removed",
        "endpoint_scope",
        "public_alias",
        "record_capture",
        "link_digest",
        "parent_hash",
        "signature",
        "roles",
        "root_id",
        "company",
        "generation",
        "catalog",
        "revision",
        "sequence",
        "same_sequence_record",
        "sequence_advance_wrong_capture",
        "clock",
        "cycle",
        "format",
        "depth",
        "size",
    ],
)
def test_changed_or_replayed_chain_never_replaces_latest_partial(
    setup, monkeypatch, problem
):
    from pathlib import Path

    r = Rotations(setup, monkeypatch)
    r.rotate("catalog-b")
    signing, _ = r.prepare("catalog-c")
    r.commit()
    config = deepcopy(r.config)
    record = config["keys"][0]
    path = Path(record["approvals"][0]["file"])
    original = path.read_bytes()
    if problem == "root_revoked":
        record.update(state="REVOKED", approvals=[])
    elif problem == "intermediate_revoked":
        config["keys"][1].update(state="REVOKED", approvals=[])
    elif problem == "missing_intermediate":
        config["keys"].pop(1)
    elif problem == "missing_own_root":
        config["keys"][1]["approvals"] = []
    elif problem == "old_root_replay":
        record["approvals"] = [r.root_receipts["catalog"]]
    elif problem == "wrong_own_root":
        config["keys"][1]["approvals"] = [r.root_receipts["catalog"]]
    elif problem == "endpoint_removed":
        r.public.pop("catalog-c")
        r.scopes.pop("catalog-c")
    elif problem == "endpoint_scope":
        r.scopes["catalog-c"] = (frozenset(["999"]), frozenset(["CHECKPOINT_CATALOG"]))
    elif problem == "public_alias":
        config["keys"][1]["publicKey"] = record["publicKey"]
    elif problem == "depth":
        monkeypatch.setattr(chain, "MAX_EDGES", 1)
    elif problem == "size":
        monkeypatch.setattr(chain, "MAX_EXPANDED", 10)
    else:
        value = json.loads(original)
        e = value["envelope"]
        if problem == "record_capture":
            e["capturedRecordDigest"] = "f" * 64
        elif problem == "link_digest":
            e["retiringHandoverDigest"] = "f" * 64
        elif problem == "parent_hash":
            e["parentDigest"] = "f" * 64
        elif problem == "signature":
            value["successorSignature"] = base64.b64encode(b"x" * 64).decode()
        elif problem == "roles":
            value["retiringSignature"], value["successorSignature"] = (
                value["successorSignature"],
                value["retiringSignature"],
            )
        elif problem in {"root_id", "catalog"}:
            from uuid import uuid4

            e["rootHandoverId" if problem == "root_id" else "catalogId"] = str(uuid4())
        elif problem == "company":
            e["workspaceId"] = "999"
        elif problem == "generation":
            e["generationId"] = "999"
        elif problem == "revision":
            e["capturedRevision"] = 1
        elif problem == "sequence":
            e["capturedSequence"] = 1
        elif problem == "sequence_advance_wrong_capture":
            e["capturedSequence"] += 1
            e["capturedRecordDigest"] = "f" * 64
        elif problem == "same_sequence_record":
            parent = json.loads(base64.b64decode(e["parent"]))["envelope"]
            e["capturedSequence"] = parent["capturedSequence"]
            e["capturedRecordDigest"] = "f" * 64
        elif problem == "clock":
            e["issuedAt"] = (setup[1]["now"] - timedelta(seconds=1)).isoformat()
        elif problem == "cycle":
            parent = json.loads(base64.b64decode(e["parent"]))["envelope"]
            e["successorKeyId"] = parent["retiringKeyId"]
            e["successorPublicDigest"] = parent["retiringPublicDigest"]
        else:
            e["version"] = True
        if problem not in {"signature", "roles"}:
            message = chain.DOMAIN + canonical(e)
            value["retiringSignature"] = base64.b64encode(
                signing["retiring_signer"].sign(b"RETIRING\0" + message)
            ).decode()
            value["successorSignature"] = base64.b64encode(
                signing["successor_signer"].sign(b"SUCCESSOR\0" + message)
            ).decode()
        raw = canonical(value)
        path.write_bytes(raw)
        record["approvals"][0]["digest"] = store.digest(raw)
    before = (setup[0] / store.PIN).read_bytes()
    with pytest.raises((ValueError, KeyError, InvalidSignature)):
        keys = r.keys(config)
        # Revoking the root also removes authority for the unchanged inner PARTIAL proof.
        store.managed_read(
            setup[0] / store.PIN,
            public_keys=keys,
            workspace_id=setup[2]["workspace_id"],
            now=setup[1]["now"],
        )
    assert (setup[0] / store.PIN).read_bytes() == before


@pytest.mark.parametrize(
    "problem",
    [
        "parent_pin",
        "unpinned_parent",
        "own_pin",
        "wrong_own_capture",
        "cas",
        "wrong_endpoint",
        "private",
        "old_scope",
        "clock",
        "stale",
        "depth",
        "source_changed",
    ],
)
def test_extension_requires_current_pinned_parent_and_actual_captured_source(
    setup, monkeypatch, problem
):
    from pathlib import Path

    r = Rotations(setup, monkeypatch)
    r.rotate("catalog-b")
    kw, _own = r.prepare("catalog-c")
    record = r.config["keys"][0]
    changes = {}
    if problem == "parent_pin":
        changes["expected_parent_digest"] = "f" * 64
    elif problem == "unpinned_parent":
        raw = Path(record["approvals"][0]["file"]).read_bytes() + b" "
        changes.update(parent_raw=raw, expected_parent_digest=store.digest(raw))
    elif problem == "own_pin":
        changes["expected_retiring_handover_digest"] = "f" * 64
    elif problem == "wrong_own_capture":
        changes["retiring_handover_raw"] = Path(
            r.root_receipts["catalog"]["file"]
        ).read_bytes()
        changes["expected_retiring_handover_digest"] = store.digest(
            changes["retiring_handover_raw"]
        )
    elif problem == "cas":
        changes["expected_pin_digest"] = "f" * 64
    elif problem == "wrong_endpoint":
        changes.update(retiring_id="catalog-c", retiring_signer=r.private["catalog-c"])
    elif problem == "private":
        changes["successor_signer"] = Ed25519PrivateKey.generate()
    elif problem == "old_scope":
        changes["context"] = kw["context"].model_copy(update={"generation_id": 999})
    elif problem == "clock":
        changes["now"] = setup[1]["now"] - timedelta(seconds=1)
    elif problem == "stale":
        changes["now"] = setup[1]["now"] + timedelta(minutes=16)
    elif problem == "depth":
        monkeypatch.setattr(chain, "MAX_EDGES", 1)
    else:
        r.current = store.publish(
            setup[0],
            context=kw["context"],
            public_keys=kw["public_keys"],
            signer=r.private["catalog-b"],
            signer_id="catalog-b",
            now=kw["now"],
            expected_pin_digest=r.current["pinDigest"],
            operation="refresh",
        )
        changes["expected_pin_digest"] = r.current["pinDigest"]
    before = {p.name: p.read_bytes() for p in setup[0].iterdir()}
    with pytest.raises((ValueError, KeyError, InvalidSignature)):
        r.extension(record, **changes)
    assert before == {p.name: p.read_bytes() for p in setup[0].iterdir()}


def test_eight_edges_work_and_ninth_rotation_does_not_mutate_source(setup, monkeypatch):
    r = Rotations(setup, monkeypatch, "FAIL")
    for index in range(1, 9):
        r.rotate(f"catalog-{index}")
    assert set(r.private) == {"catalog-8"}
    before = (setup[0] / store.PIN).read_bytes()
    r.prepare("catalog-9")
    with pytest.raises(ValueError, match="depth"):
        r.commit()
    assert (setup[0] / store.PIN).read_bytes() == before
    current, _ = store.managed_read(
        setup[0] / store.PIN,
        public_keys=r.keys(),
        workspace_id=setup[2]["workspace_id"],
        now=setup[1]["now"],
    )
    assert current.signer_key_id == "catalog-8" and current.records[0].result == "FAIL"


@pytest.mark.parametrize(
    "problem",
    ["duplicate_json", "recursive", "oversize", "extra", "base64", "unknown_kind"],
)
def test_bounded_strict_chain_parsing_never_changes_source(setup, monkeypatch, problem):
    from pathlib import Path

    r = Rotations(setup, monkeypatch)
    r.rotate("catalog-b")
    r.rotate("catalog-c")
    config = deepcopy(r.config)
    approval = config["keys"][0]["approvals"][0]
    path = Path(approval["file"])
    raw = path.read_bytes()
    if problem == "duplicate_json":
        raw = raw.replace(b'"version":1', b'"version":1,"version":1', 1)
    elif problem == "recursive":
        raw = b"[" * 2000 + b"]" * 2000
    elif problem == "oversize":
        raw = b"x" * (handover.MAX_BYTES + 1)
    else:
        value = json.loads(raw)
        if problem == "extra":
            value["envelope"]["acceptancePass"] = True
        elif problem == "base64":
            value["envelope"]["parent"] = "not-base64"
        else:
            value["envelope"]["kind"] = "UNBOUNDED_DELEGATION"
        raw = canonical(value)
    path.write_bytes(raw)
    approval["digest"] = store.digest(raw)
    before = (setup[0] / store.PIN).read_bytes()
    with pytest.raises((ValueError, RecursionError)):
        r.keys(config)
    assert (setup[0] / store.PIN).read_bytes() == before


@pytest.mark.parametrize(
    "problem", ["omitted_snapshot", "extra_snapshot", "extra_recovery", "backdated_own"]
)
def test_dual_signed_retiring_handover_cannot_omit_or_add_source_originals(
    setup, monkeypatch, problem
):
    from pathlib import Path

    r = Rotations(setup, monkeypatch)
    r.rotate("catalog-b")
    r.current = store.publish(
        setup[0],
        context=setup[1]["context"],
        public_keys=r.keys(),
        signer=r.private["catalog-b"],
        signer_id="catalog-b",
        now=setup[1]["now"],
        expected_pin_digest=r.current["pinDigest"],
        operation="refresh",
    )
    kw, own = r.prepare("catalog-c")
    value = json.loads(Path(own["file"]).read_bytes())
    envelope = value["envelope"]
    if problem == "omitted_snapshot":
        envelope["snapshots"].pop(0)
    elif problem == "extra_snapshot":
        original = next(
            p
            for p in setup[0].glob("catalog-*.json")
            if int(store.NAME.fullmatch(p.name)[1]) == 1
        )
        envelope["snapshots"].insert(
            0,
            {
                "version": 1,
                "revision": 1,
                "digest": store.digest(original.read_bytes()),
            },
        )
    elif problem == "extra_recovery":
        envelope["recoveryProofs"].append("f" * 64)
    else:
        envelope["issuedAt"] = (setup[1]["now"] - timedelta(seconds=1)).isoformat()
    message = handover.DOMAIN + canonical(envelope)
    value["retiringSignature"] = base64.b64encode(
        kw["retiring_signer"].sign(b"RETIRING\0" + message)
    ).decode()
    value["successorSignature"] = base64.b64encode(
        kw["successor_signer"].sign(b"SUCCESSOR\0" + message)
    ).decode()
    raw = canonical(value)
    before = (setup[0] / store.PIN).read_bytes()
    with pytest.raises(ValueError):
        r.extension(
            r.config["keys"][0],
            retiring_handover_raw=raw,
            expected_retiring_handover_digest=store.digest(raw),
        )
    assert (setup[0] / store.PIN).read_bytes() == before
