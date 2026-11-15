#!/usr/bin/env python3
"""ERP-1a: 승인된 목표 설계(schema-target.json)의 ERP 보강을 제품 설계(schema.json)로 옮긴다.

ERP는 FS-005e로 영업 → 출하 → 매출 → 채권·수금까지 돌고 있다. 이 단계는 그 DB를 목표 설계(DSN-11)까지 올린다.
  - 새 표 36개 (부서·담당자·프로젝트·단가 그룹, 판매/구매 반품, 구매 요청·발주, 채권·채무 조정,
    전표·지출결의, 회계 기간·기초 잔액, 원가 계산, 매입 세금계산서·부가세 신고,
    계좌·카드·자금 계획·예산·고정자산)
  - 기존 표 변경 10개 (거래처 상세·여신·단가 그룹, 품목 규격·표준 단가, 수주 할인,
    매입 전표 종류·발주 연결, 수금·지급 계좌, 계정 분류·정상 잔액, 세금계산서 전송 상태,
    분개 규칙 거래 종류 14종) — 제약 제자리 교체

**이 단계는 DSN-11 범위만 옮긴다.** 목표 파일에는 다음이 더 있지만 각자의 작업으로 남긴다:
  - `erp.approval_policy`·`erp.approval_evidence` — DSN-31 F44 ERP 확정 통제(W2b 배정)
  - PLM·CRM·SCM 참조 칼럼 — 그 솔루션을 만들 때 함께 넣는다(지금 읽는 코드가 없다)

본보기는 `apply_bems1.py`다(`sync_nullable()` 포함). 제약·관계는 **배열 끝에 붙이고**, 교체하는
제약만 제자리에서 바꾼다(순번이 곧 DB 제약 이름이라 끼워 넣으면 기존 DB와 어긋난다).

마이그레이션은 tools/build_migration.py --previous 가 이 결과로 만든다. 멱등(두 번 돌려도 같다).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / "docs/db/schema-metadata/schema.json"
TARGET = ROOT / "docs/db/schema-metadata/schema-target.json"
VERSION = "0.36.0"
TASK = "ERP-1a"
DATE = "2026-11-15"
SCHEMA = "erp"
CHANGE = (
    "ERP 보강: 새 표 36개(부서·담당자·프로젝트·단가 그룹, 판매/구매 반품, 구매 요청·발주, "
    "채권·채무 조정, 전표·지출결의, 회계 기간·기초 잔액, 원가 계산, 매입 세금계산서·부가세 신고, "
    "계좌·카드·자금 계획·예산·고정자산)와 기존 표 변경 10개(거래처 상세·여신·단가 그룹, 품목 규격·"
    "표준 단가, 수주 할인, 매입 전표 종류·발주 연결, 수금·지급 계좌, 계정 분류·정상 잔액, "
    "세금계산서 전송 상태, 분개 규칙 14종). 목표 설계 DSN-11에서 그대로 옮김"
)
STATUS = "마이그레이션 erp1 적용 대상"
# 칼럼이 늘어 제자리 교체 대상을 칼럼으로 찾을 수 없는 제약(QMS-1a의 특례).
WIDENED: set[tuple[str, str]] = set()
# DSN-11 범위 밖이라 이번에 옮기지 않는 표·칼럼. 각자의 작업에서 넣는다.
DEFERRED_TABLES = {"erp.approval_policy", "erp.approval_evidence"}
DEFERRED_COLUMNS = {
    ("erp.item", "plm_part_no"),
    ("erp.item", "plm_revision"),
    ("erp.partner", "crm_account_code"),
    ("erp.quotation", "crm_quote_request_no"),
    ("erp.sales_plan", "scm_forecast_ref"),
}
# 없어지는 제약을 어느 새 제약이 **제자리에서** 잇는지. 칼럼이 달라져 자동으로 못 짝짓는 것만 적는다.
# 순번이 곧 DB 제약 이름이라, 끼워 넣지 않고 그 자리를 그대로 쓴다.
REPLACEMENTS = {
    # 세금계산서 2상태 → 4상태(전송 흉내, Q6)
    ("erp.tax_invoice", "CHECK", ("status", "approval_no", "issued_on")): (
        "status",
        "approval_no",
        "issued_on",
        "transmitted_at",
        "cancelled_at",
    ),
    # 고정 7계정 정의 → 계정 분류·정상 잔액(F41). 코드 형식 CHECK는 뒤에 새로 붙는다.
    ("erp.account", "CHECK", ("account_code", "account_name")): (
        "account_class",
        "normal_side",
    ),
    # 고정 10조합 → 거래 종류 14종 값 CHECK(F43). 나머지 값 CHECK는 뒤에 새로 붙는다.
    (
        "erp.posting_rule",
        "CHECK",
        ("transaction_kind", "line_no", "entry_side", "account_code", "amount_basis"),
    ): ("transaction_kind",),
}


def key(c: dict[str, Any]) -> tuple:
    return (
        c["table"],
        c["kind"],
        tuple(c.get("columns") or []),
        c.get("expression", ""),
    )


def relation_key(r: dict[str, Any]) -> tuple:
    return (r["source"], tuple(r["columns"]), r["target"], tuple(r["target_columns"]))


def sync_nullable(current: dict, wanted: list[dict]) -> list[str]:
    """기존 칼럼의 NULL 허용을 목표와 맞춘다. 푸는 방향만 허용한다.

    `spc2`·`cmms2`가 이것을 빠뜨려 따로 생겼다. NOT NULL로 조이는 변경은 기존 행이
    비어 있지 않은지 확인해야 하므로 여기서 하지 않고 멈춘다.
    """
    goals = {t["name"]: {c["name"]: c for c in t["columns"]} for t in wanted}
    loosened = []
    for table in current["tables"]:
        columns = goals.get(table["name"])
        if columns is None:
            continue
        for column in table["columns"]:
            goal = columns.get(column["name"])
            if goal is None or goal["nullable"] == column["nullable"]:
                continue
            if not goal["nullable"]:
                raise SystemExit(
                    f"{table['name']}.{column['name']}: "
                    "NOT NULL로 조이는 변경은 기존 행 확인이 필요하다"
                )
            column["nullable"] = True
            loosened.append(f"{table['name']}.{column['name']}")
    return loosened


def apply(current: dict, target: dict) -> bool:
    """current를 제자리에서 바꾸고, 바뀌었으면 True."""
    before = json.dumps(current, ensure_ascii=False, sort_keys=True)
    have = {t["name"]: t for t in current["tables"]}
    wanted = [
        t
        for t in target["tables"]
        if t["name"].startswith(f"{SCHEMA}.") and t["name"] not in DEFERRED_TABLES
    ]

    # 1) 새 표는 통째로, 기존 표는 빠진 칼럼만 목표 순서대로 붙인다.
    for table in wanted:
        mine = have.get(table["name"])
        if mine is None:
            current["tables"].append(json.loads(json.dumps(table)))
            continue
        existing = {c["name"] for c in mine["columns"]}
        for column in table["columns"]:
            if column["name"] in existing:
                continue
            if (table["name"], column["name"]) in DEFERRED_COLUMNS:
                continue
            mine["columns"].append(json.loads(json.dumps(column)))

    sync_nullable(current, wanted)

    names = {t["name"] for t in wanted}
    mine_keys = {key(c) for c in current["constraints"]}

    def deferred(c: dict[str, Any]) -> bool:
        """미루는 칼럼을 가리키는 제약은 그 칼럼과 함께 미룬다."""
        return any((c["table"], col) in DEFERRED_COLUMNS for col in c.get("columns") or [])

    fresh = [
        c
        for c in target["constraints"]
        if c["table"] in names and key(c) not in mine_keys and not deferred(c)
    ]

    # 2) 없어지는 제약은 같은 표·같은 칼럼의 새 제약으로 **제자리에서** 바꾼다.
    #    순번이 곧 DB의 제약 이름이라, 끼워 넣거나 지우면 기존 DB와 어긋난다.
    target_keys = {key(c) for c in target["constraints"] if c["table"] in names}
    for index, old in enumerate(current["constraints"]):
        if old["table"] not in names or key(old) in target_keys:
            continue
        mapped = REPLACEMENTS.get(
            (old["table"], old["kind"], tuple(old["columns"]))
        )
        same = [
            c
            for c in fresh
            if c["table"] == old["table"]
            and c["kind"] == old["kind"]
            and tuple(c["columns"]) == (mapped or tuple(old["columns"]))
        ]
        if not same and (old["table"], old["kind"]) in WIDENED:
            # 칸이 늘어난 제약은 칼럼으로 못 잡는다. 표·종류가 하나뿐일 때만 짝지어 제자리에 둔다.
            same = [
                c
                for c in fresh
                if c["table"] == old["table"] and c["kind"] == old["kind"]
            ]
        if len(same) == 1:
            current["constraints"][index] = json.loads(json.dumps(same[0]))
            fresh.remove(same[0])
        else:
            raise SystemExit(
                f"교체 대상이 하나가 아니다: {old['table']} {old['columns']} → {len(same)}건"
            )

    # 3) 상태·코드 목록도 목표와 맞춘다. 표만 옮기고 빠뜨리면 설계 검증이 잡는다(세금계산서 전송 Q6).
    for field, mine_key in (
        ("states", lambda x: (x["table"], x["column"])),
        ("code_lists", lambda x: (x["target"], x["column"])),
    ):
        mine = {mine_key(x): i for i, x in enumerate(current[field])}
        for wanted_row in target[field]:
            if not mine_key(wanted_row)[0].startswith(f"{SCHEMA}."):
                continue
            if mine_key(wanted_row)[0] in DEFERRED_TABLES:
                continue
            index = mine.get(mine_key(wanted_row))
            if index is None:
                current[field].append(json.loads(json.dumps(wanted_row)))
            else:
                current[field][index] = json.loads(json.dumps(wanted_row))

    # 4) 남은 새 제약·관계는 배열 끝에 붙인다.
    current["constraints"].extend(json.loads(json.dumps(c)) for c in fresh)
    mine_relations = {relation_key(r) for r in current["relations"]}
    current["relations"].extend(
        json.loads(json.dumps(r))
        for r in target["relations"]
        if r["source"] in names
        and r["target"] not in DEFERRED_TABLES
        and relation_key(r) not in mine_relations
        and not any((r["source"], col) in DEFERRED_COLUMNS for col in r["columns"])
    )

    if json.dumps(current, ensure_ascii=False, sort_keys=True) == before:
        return False
    current["version"] = VERSION
    current["task"] = TASK
    current["date"] = DATE
    current["change_log"].append(
        {
            "version": VERSION,
            "task": TASK,
            "date": DATE,
            "change": CHANGE,
            "status": STATUS,
        }
    )
    target["base_task"] = TASK
    return True


def main() -> None:
    current = json.loads(CURRENT.read_text(encoding="utf-8"))
    target = json.loads(TARGET.read_text(encoding="utf-8"))
    changed = apply(current, target)
    if changed:
        CURRENT.write_text(
            json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        TARGET.write_text(
            json.dumps(target, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    tables = sum(1 for t in current["tables"] if t["name"].startswith(f"{SCHEMA}."))
    print(
        json.dumps(
            {
                "changed": changed,
                "version": current["version"],
                "erp_tables": tables,
                "tables": len(current["tables"]),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
