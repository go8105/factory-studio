"""Read pinned Git metadata and write a design-only GW/main integration plan."""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVISION = "gw_main_ready02_merge"
SUFFIX = {
    "PK": "pk",
    "UK": "uk",
    "CHECK": "check",
    "INDEX": "idx",
    "UK_PARTIAL": "uidx",
    "UNIQUE_INDEX": "uidx",
}


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def load(ref: str, filename: str) -> dict:
    return json.loads(git("show", f"{ref}:docs/db/schema-metadata/{filename}"))


def signature(value: dict) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def append_gw_delta(base: list, gw: list, main: list) -> list:
    before, ours, theirs = (set(map(signature, values)) for values in [base, gw, main])
    if before - ours:
        raise ValueError("GW removed/changed records: manual plan required")
    return copy.deepcopy(main + [v for v in gw if signature(v) not in before | theirs])


def candidate(base: dict, gw: dict, main: dict) -> dict:
    original = {v["name"]: v for v in base["tables"]}
    ours = {v["name"]: v for v in gw["tables"]}
    theirs = {v["name"]: v for v in main["tables"]}
    if original.keys() - ours.keys() or original.keys() - theirs.keys():
        raise ValueError("table removal: manual plan required")
    if any(
        ours[name] != theirs[name]
        for name in (ours.keys() & theirs.keys()) - original.keys()
    ):
        raise ValueError("new table differs between parents: manual plan required")
    result = copy.deepcopy(main)
    result["tables"] = []
    for table in main["tables"]:
        name = table["name"]
        if name in original and ours[name] != original[name]:
            if theirs[name] != original[name] and ours[name] != theirs[name]:
                raise ValueError("table modified on both parents: " + name)
            table = ours[name]
        result["tables"].append(copy.deepcopy(table))
    result["tables"].extend(
        copy.deepcopy([v for v in gw["tables"] if v["name"] not in theirs])
    )
    for key in ["constraints", "relations"]:
        result[key] = append_gw_delta(base[key], gw[key], main[key])
    for key in ["code_lists", "states", "sources"]:
        if gw[key] != main[key]:
            raise ValueError("shared metadata differs: " + key)
    result.update(
        review_only=True, migration_revision=None, proposed_migration_revision=REVISION
    )
    return result


def revisions(ref: str) -> dict:
    result = {}
    for name in (
        git("ls-tree", "-r", "--name-only", ref, "backend/alembic/versions")
        .decode()
        .splitlines()
    ):
        if not name.endswith(".py"):
            continue
        values = {}
        for node in ast.parse(git("show", f"{ref}:{name}")).body:
            pairs = (
                [(t, node.value) for t in node.targets]
                if isinstance(node, ast.Assign)
                else [(node.target, node.value)]
                if isinstance(node, ast.AnnAssign)
                else []
            )
            for target, value in pairs:
                if isinstance(target, ast.Name) and target.id in {
                    "revision",
                    "down_revision",
                }:
                    values[target.id] = ast.literal_eval(value)
        if values.get("revision"):
            result[values["revision"]] = {
                "parent": values.get("down_revision"),
                "path": name,
            }
    return result


def heads(values: dict) -> list:
    parents = {
        p
        for value in values.values()
        for p in (
            value["parent"] if isinstance(value["parent"], tuple) else [value["parent"]]
        )
    }
    return sorted(set(values) - parents)


def renames(parent: dict, merged: dict) -> dict:
    output = {}
    for key in ["constraints", "relations"]:
        target = {signature(value): i for i, value in enumerate(merged[key])}
        rows = []
        for i, value in enumerate(parent[key]):
            j = target.get(signature(value))
            if (
                j is None
                or i == j
                or (key == "constraints" and value["kind"] not in SUFFIX)
            ):
                continue
            old, new = (
                (f"r{i}_fk", f"r{j}_fk")
                if key == "relations"
                else (f"c{i}_{SUFFIX[value['kind']]}", f"c{j}_{SUFFIX[value['kind']]}")
            )
            rows.append(
                {
                    "table": value.get("table", value.get("source")),
                    "from": old,
                    "to": new,
                    "kind": value.get("kind", "FK"),
                    "definition": value,
                }
            )
        output[key] = rows
    return output


def structural_audit(d: dict) -> dict:
    tables = {t["name"]: t for t in d["tables"]}
    if len(tables) != len(d["tables"]):
        raise ValueError("duplicate tables")
    columns = {n: {c["name"] for c in t["columns"]} for n, t in tables.items()}
    for name, table in tables.items():
        if len(columns[name]) != len(table["columns"]):
            raise ValueError("duplicate columns")
    for rule in d["constraints"]:
        if not set(rule["columns"]) <= columns[rule["table"]]:
            raise ValueError("unknown constraint column")
    edges = set()
    for relation in d["relations"]:
        if relation["source"].split(".")[0] != relation["target"].split(".")[
            0
        ] and relation["target"] not in {"core.workspace", "core.data_generation"}:
            raise ValueError("forbidden cross-solution FK")
        if (
            not set(relation["columns"]) <= columns[relation["source"]]
            or not set(relation["target_columns"]) <= columns[relation["target"]]
        ):
            raise ValueError("unknown FK column")
        identity = signature({k: v for k, v in relation.items() if k != "note"})
        if identity in edges:
            raise ValueError("duplicate FK")
        edges.add(identity)
        if relation["on_delete"] != "RESTRICT" or relation["on_update"] != "RESTRICT":
            raise ValueError("non-RESTRICT FK")
    return {
        "tables": len(tables),
        "columns": sum(len(v) for v in columns.values()),
        "relations": len(edges),
        "constraintKinds": dict(Counter(v["kind"] for v in d["constraints"])),
    }


def preserved_duplicates(gw: dict, main: dict, merged: dict) -> list:
    def physical(d):
        return Counter(
            signature({k: v for k, v in r.items() if k != "reason"})
            for r in d["constraints"]
            if r["kind"] in SUFFIX
        )

    ours, theirs, target = (physical(d) for d in [gw, main, merged])
    result = []
    for key, count in target.items():
        if count > max(ours[key], theirs[key]):
            raise ValueError("new duplicate physical constraint")
        if count > 1:
            value = json.loads(key)
            result.append(
                {
                    "table": value["table"],
                    "kind": value["kind"],
                    "columns": value["columns"],
                    "count": count,
                    "gwCount": ours[key],
                    "mainCount": theirs[key],
                }
            )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gw-ref", required=True)
    parser.add_argument("--main-ref", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--draft-directory", type=Path, required=True)
    args = parser.parse_args()
    draft = args.draft_directory.resolve()
    if not draft.is_relative_to(ROOT / "work"):
        raise ValueError("drafts must stay under work/")
    gw_ref = git("rev-parse", args.gw_ref).decode().strip()
    main_ref = git("rev-parse", args.main_ref).decode().strip()
    base = git("merge-base", gw_ref, main_ref).decode().strip()
    gw, upstream, ancestor = (load(r, "schema.json") for r in [gw_ref, main_ref, base])
    if gw["version"] != "0.28.0" or upstream["version"] != "0.33.0":
        raise ValueError(
            "metadata versions changed: review proposed version headers again"
        )
    merged = candidate(ancestor, gw, upstream)
    merged.update(task="GW-READY-02-INTEGRATION-REVIEW", version="0.34.0-review")
    target = candidate(
        load(base, "schema-target.json"),
        load(gw_ref, "schema-target.json"),
        load(main_ref, "schema-target.json"),
    )
    target.update(
        migration_revision=None,
        base_task=merged["task"],
        version="target-0.22.0-review",
        proposed_migration_revision=None,
    )
    ours, theirs = revisions(gw_ref), revisions(main_ref)
    if (
        REVISION in ours
        or REVISION in theirs
        or len(heads(ours)) != 1
        or len(heads(theirs)) != 1
    ):
        raise ValueError("revision identity or parent heads changed")
    maps = {
        label: renames(parent, merged)
        for label, parent in [("gw", gw), ("main", upstream)]
    }
    target_tables = {t["name"]: t for t in target["tables"]}
    target_differences, target_only = [], []
    for table in merged["tables"]:
        current_columns = {c["name"]: c for c in table["columns"]}
        planned_columns = {
            c["name"]: c for c in target_tables[table["name"]]["columns"]
        }
        if current_columns.keys() - planned_columns.keys():
            raise ValueError("implemented column missing from target")
        if planned_columns.keys() - current_columns.keys():
            target_only.append(
                {
                    "table": table["name"],
                    "columns": sorted(planned_columns.keys() - current_columns.keys()),
                }
            )
        for name in sorted(current_columns.keys() & planned_columns.keys()):
            fields = [
                k
                for k in ["type", "nullable", "default"]
                if current_columns[name].get(k) != planned_columns[name].get(k)
            ]
            if fields:
                target_differences.append(
                    {
                        "column": table["name"] + "." + name,
                        "fields": fields,
                        "current": {k: current_columns[name].get(k) for k in fields},
                        "target": {k: planned_columns[name].get(k) for k in fields},
                    }
                )
    draft.mkdir(parents=True, exist_ok=True)
    for name, value in [("current-draft.json", merged), ("target-draft.json", target)]:
        (draft / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n"
        )
    report = {
        "kind": "GW_MAIN_INTEGRATION_DESIGN",
        "version": 1,
        "gwRef": gw_ref,
        "mainRef": main_ref,
        "mergeBase": base,
        "proposedCurrentMetadataHeader": {
            "task": "GW-READY-02-INTEGRATION",
            "version": "0.34.0",
            "migration_revision": REVISION,
        },
        "proposedTargetMetadataHeader": {
            "task": "DSN-90",
            "base_task": "GW-READY-02-INTEGRATION",
            "version": "target-0.22.0",
            "migration_revision": None,
            "target": True,
        },
        "proposedRevision": REVISION,
        "proposedParents": heads(ours) + heads(theirs),
        "applied": False,
        "ready": False,
        "signedEvidence": False,
        "canonicalMetadataChanged": False,
        "documentaryMergePending": ["date", "basis", "status", "change_log"],
        "candidateDdlValidated": False,
        "preservedPhysicalDuplicates": preserved_duplicates(gw, upstream, merged),
        "preservedTargetPhysicalDuplicates": preserved_duplicates(
            load(gw_ref, "schema-target.json"),
            load(main_ref, "schema-target.json"),
            target,
        ),
        "currentStructuralAudit": structural_audit(merged),
        "targetStructuralAudit": structural_audit(target),
        "normalizationByParentMetadata": maps,
        "mainMetadataRevision": upstream["migration_revision"],
        "mainActualHeads": heads(theirs),
        "targetStructuralDifferences": target_differences,
        "targetOnlyColumnGroups": target_only,
        "existingRevisionByteDifferences": [
            r
            for r in sorted(ours.keys() & theirs.keys())
            if git("show", gw_ref + ":" + ours[r]["path"])
            != git("show", main_ref + ":" + theirs[r]["path"])
        ],
        "draftDigests": {
            name: hashlib.sha256((draft / name).read_bytes()).hexdigest()
            for name in ["current-draft.json", "target-draft.json"]
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "designOnly": True,
                "current": report["currentStructuralAudit"],
                "target": report["targetStructuralAudit"],
                "renamesByParent": {
                    k: {kind: len(values) for kind, values in rows.items()}
                    for k, rows in maps.items()
                },
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
