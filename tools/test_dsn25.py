"""DSN-25: CRM 목표 설계 계약 — 견적·수주·클레임 테이블이 CRM으로 오거나, ERP 처리 상태를 저장하거나, ERP 수주 없는 수주·품질 외 QMS 전환이면 실패한다."""

import copy
import json
import unittest
from pathlib import Path

from validate_db_design import validate_crm_dsn25

ROOT = Path(__file__).resolve().parents[1]


class CrmTargetTest(unittest.TestCase):
    def setUp(self):
        self.target = json.loads(
            (ROOT / "docs/db/schema-metadata/schema-target.json").read_text(
                encoding="utf-8"
            )
        )

    def test_contract_holds(self):
        self.assertEqual(validate_crm_dsn25(self.target), [])
        self.assertEqual(
            sum(t["name"].startswith("crm.") for t in self.target["tables"]), 13
        )

    def test_rejects_regressions(self):
        d = copy.deepcopy(self.target)
        d["tables"].append({"name": "crm.claim", "columns": []})
        next(t for t in d["tables"] if t["name"] == "crm.quote_request")[
            "columns"
        ].append({"name": "imported_at"})
        d["constraints"] = [
            c
            for c in d["constraints"]
            if "erp_order_no IS NOT NULL)" not in c["expression"]
            and c["expression"] != "status <> 'TRANSFERRED' OR kind = 'QUALITY'"
        ]
        errors = validate_crm_dsn25(d)
        for word in (
            "claims to QMS",
            "not stored",
            "won needs ERP order",
            "only quality",
        ):
            self.assertTrue(any(word in e for e in errors), word)


if __name__ == "__main__":
    unittest.main()
