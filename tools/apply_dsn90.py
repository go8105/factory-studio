"""DSN-90: 통합 검증에서 찾은 목표 DB 빈칸을 메운다(멱등, apply_dsn30 다음).

근거: docs/plan/통합검증_DSN-90.md 3장. "X에서 가져오기"는 받는 쪽이 원천 번호를 스냅샷해야
① 같은 원천을 두 번 가져오지 않고(멱등) ② 원천 쪽 `*_imports()` 조회(가져간 현황)를 만들 수 있다.
교차 FK는 두지 않는다(코드 문자열, FS-013).
"""

import json
from pathlib import Path

from apply_fs023a import c, col, uk_partial

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs/db/schema-metadata/schema-target.json"


def ref(name, label, rule, size=40):
    return col(name, label, f"varchar({size})", nullable=True, rule=f"DSN-90 {rule}")


PLM = [
    ref("plm_part_no", "PLM 부품 번호", "PLM에서 가져오기 — 배포 리비전 스냅샷"),
    ref("plm_revision", "PLM 리비전", "plm_part_no와 함께", 10),
]
EXT_COLUMNS = {
    "erp.partner": [
        ref("crm_account_code", "CRM 고객사 코드", "CRM에서 가져오기(DSN-25 Q1)", 30)
    ],
    "erp.quotation": [
        ref(
            "crm_quote_request_no",
            "CRM 견적 요청 번호",
            "CRM 견적 요청 → 견적 초안(DSN-25 Q2)",
            30,
        )
    ],
    "erp.sales_plan": [
        ref("scm_forecast_ref", "SCM 확정 예측", "SCM에서 가져오기(DSN-26 Q3), 추적용")
    ],
    "erp.item": PLM,
    "mes.item": PLM,
    "wms.item": PLM,
    "mes.bom_version": [
        ref(
            "plm_bom_ref",
            "PLM E-BOM",
            "'부품 번호:리비전' — 제조 BOM의 출처(DSN-24 Q4)",
            50,
        )
    ],
    "qms.claim": [
        ref(
            "crm_inquiry_no",
            "CRM 품질 문의 번호",
            "CRM 품질 문의 → 클레임(DSN-25 Q4)",
            30,
        )
    ],
    "qms.change_notice": [
        ref("plm_eco_no", "PLM ECO 번호", "PLM 배포 ECO → 4M 후보(DSN-24 Q3)", 30)
    ],
}
CONSTRAINTS = [
    uk_partial(
        "erp.partner",
        ["crm_account_code"],
        "crm_account_code IS NOT NULL",
        "CRM 고객사당 거래처 1건",
    ),
    uk_partial(
        "erp.quotation",
        ["crm_quote_request_no"],
        "crm_quote_request_no IS NOT NULL AND revision_no = 1",
        "CRM 견적 요청당 견적 1건(개정은 같은 견적)",
    ),
    uk_partial(
        "qms.claim",
        ["crm_inquiry_no"],
        "crm_inquiry_no IS NOT NULL",
        "CRM 문의당 클레임 1건",
    ),
    uk_partial(
        "qms.change_notice",
        ["plm_eco_no", "item_code"],
        "plm_eco_no IS NOT NULL AND status <> 'REJECTED'",
        "ECO·품목당 진행 4M 1건",
    ),
    uk_partial(
        "qms.ncr",
        ["origin", "source_ref"],
        "source_ref IS NOT NULL",
        "원천(SPC 이탈 등)당 NCR 1건",
    ),
]
for t in ("erp.item", "mes.item", "wms.item"):
    CONSTRAINTS.append(
        c(
            t,
            "CHECK",
            ["plm_part_no", "plm_revision"],
            "(plm_part_no IS NULL) = (plm_revision IS NULL)",
            "PLM 번호·리비전 함께",
        )
    )

# 기존 제약 교체 — (표, 옛 문자열, 새 문자열). 모두 찾지 못하면 아무것도 바꾸지 않는다.
INV_OLD = "invoice_kind IN ('PO_RECEIPT', 'DIRECT', 'SUBCONTRACT')"
INV_NEW = (
    "invoice_kind IN ('PO_RECEIPT', 'DIRECT', 'SUBCONTRACT', 'FREIGHT', 'INDIRECT')"
)
DOC_LIST = "'ERP_SALES_RETURN', 'ERP_PURCHASE_RETURN'"
DOC_LIST_NEW = "'ERP_SALES_RETURN', 'ERP_PURCHASE_RETURN', 'CMMS_ISSUE'"
REPLACE = [
    ("erp.purchase_invoice", INV_OLD, INV_NEW, 1),
    ("wms.stock_document", DOC_LIST, DOC_LIST_NEW, 2),
]


def apply(d):
    """목표 dict를 제자리에서 바꾸고, 바뀌었으면 True."""
    if not d.get("target"):
        raise SystemExit("apply_dsn90은 schema-target.json에만 적용한다")
    tables = {t["name"]: t for t in d["tables"]}
    if "hr.employee" not in tables:
        raise SystemExit("apply_dsn30을 먼저 적용한다")
    if any(x["name"] == "crm_account_code" for x in tables["erp.partner"]["columns"]):
        return False
    missing = set(EXT_COLUMNS) - set(tables)
    hits = {
        (t, old): [
            x
            for x in d["constraints"]
            if x["table"] == t and old in x.get("expression", "")
        ]
        for t, old, _, _ in REPLACE
    }
    wrong = {
        k: len(v) for (k, v), (_, _, _, n) in zip(hits.items(), REPLACE) if len(v) != n
    }
    if missing or wrong:
        raise SystemExit(f"대상이 없다: 표 {missing}, 제약 개수 {wrong}")
    for name, columns in EXT_COLUMNS.items():
        cols = tables[name]["columns"]
        at = len(cols) - 1 if cols[-1]["name"] == "created_at" else len(cols)
        cols[at:at] = [dict(x) for x in columns]
    for (t, old), found in hits.items():
        new = next(n for tt, o, n, _ in REPLACE if (tt, o) == (t, old))
        for x in found:
            x["expression"] = x["expression"].replace(old, new)
    for code in d["code_lists"]:
        if (
            code["target"] == "erp.purchase_invoice"
            and code["column"] == "invoice_kind"
        ):
            code["values"] = [
                *code["values"],
                *(v for v in ("FREIGHT", "INDIRECT") if v not in code["values"]),
            ]
        if (
            code["target"] == "wms.stock_document"
            and code["column"] == "document_type"
            and "CMMS_ISSUE" not in code["values"]
        ):
            code["values"] = [*code["values"], "CMMS_ISSUE"]
    d["constraints"].extend(CONSTRAINTS)
    d.update(version="target-0.20.0", task="DSN-90", date="2026-10-05")
    d["change_log"].append(
        dict(
            version="target-0.20.0",
            task="DSN-90",
            date="2026-10-05",
            change="통합 검증 보정: 가져오기 원천 번호 칸(ERP 거래처·견적·판매계획, ERP·MES·WMS 품목 PLM 리비전, MES BOM, QMS 클레임·4M) + 멱등 UK, QMS NCR 원천당 1건, ERP 매입 종류 FREIGHT(TMS 운송비)·INDIRECT(ELB 비재고), WMS 문서 CMMS_ISSUE(정비 부품 출고). 교차 FK 0",
            status="설계 전용",
        )
    )
    return True


def main():
    d = json.loads(TARGET.read_text(encoding="utf-8"))
    changed = apply(d)
    if changed:
        TARGET.write_text(
            json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(
        json.dumps(
            dict(
                changed=changed,
                tables=len(d["tables"]),
                constraints=len(d["constraints"]),
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
