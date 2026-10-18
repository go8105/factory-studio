"""GW-READY-01 제안 문서만 검사한다. DB 접속/현재 명세 변경 없음."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate():
    data = json.loads(
        (ROOT / "docs/modules/gw/review/schema-proposal.json").read_text()
    )
    current = json.loads((ROOT / "docs/db/schema-metadata/schema.json").read_text())
    errors = []
    proposed = data["tables"]
    old = {t["name"]: {c["name"] for c in t["columns"]} for t in current["tables"]}
    extension_names = {"core.app_user", "core.auth_session"}
    new = [t for t in proposed if t["name"] not in extension_names]
    extended = [t for t in proposed if t["name"] in extension_names]
    if len(new) != 9 or len(extended) != 2:
        errors.append("신규9표/기존2표 확장 기준과 다릅니다.")
    if len({t["name"] for t in proposed}) != len(proposed):
        errors.append("제안 표 이름 중복")
    if current["version"] == data["current_schema"]:
        if len(current["tables"]) != data["current_tables"]:
            errors.append("현재 기준 표 수와 제안 기준 불일치")
    elif not all(t["name"] in old for t in proposed):
        errors.append("승인 후 명세에 제안 표가 일부 누락되어 재대조 필요")
    if current["version"] != data["current_schema"]:
        applied = {
            t["name"]: {c["name"]: c for c in t["columns"]} for t in current["tables"]
        }
        for table in proposed:
            for column in table["columns"]:
                actual = applied.get(table["name"], {}).get(column["name"])
                if actual is None or any(
                    actual[key] != column[key] for key in ("type", "nullable")
                ):
                    errors.append(
                        table["name"]
                        + "."
                        + column["name"]
                        + ": 승인 명세와 적용 명세 불일치"
                    )
    columns = {name: set(names) for name, names in old.items()}
    for table in proposed:
        name = table["name"]
        names = [c["name"] for c in table["columns"]]
        if len(names) != len(set(names)) or not all(n.isidentifier() for n in names):
            errors.append(name + ": 컬럼 이름 오류/중복")
        if any(
            c["type"] == "UNKNOWN" or not isinstance(c["nullable"], bool)
            for c in table["columns"]
        ):
            errors.append(name + ": 타입/NULL 명세 오류")
        if name.startswith("gw.") and not {
            "id",
            "workspace_id",
            "generation_id",
        } <= set(names):
            errors.append(name + ": S 범위 누락")
        columns.setdefault(name, set()).update(names)
    relations = data["relations"]
    if len(relations) != 19:
        errors.append("제안 FK19개 기준과 다름")
    for r in relations:
        source, target = r["source"], r["target"]
        if not set(r["columns"]) <= columns.get(source, set()) or not set(
            r["target_columns"]
        ) <= columns.get(target, set()):
            errors.append(source + ": FK 대상/컬럼 누락")
        if source.split(".")[0] != target.split(".")[0] and target not in {
            "core.workspace",
            "core.data_generation",
        }:
            errors.append(source + ": 허용되지 않은 업무 교차 FK")
        if r["on_delete"] != "RESTRICT" or r["on_update"] != "RESTRICT":
            errors.append(source + ": 참조 변경 정책 오류")
    return {
        "task": data["task"],
        "proposal_only": True,
        "new_tables": len(new),
        "extended_tables": len(extended),
        "proposed_foreign_keys": len(relations),
        "current_tables": len(current["tables"]),
        "errors": errors,
    }


if __name__ == "__main__":
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(bool(result["errors"]))
