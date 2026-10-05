"""DSN-27: ELB 목표 설계 계약 — ELB에 발주·매입·재고 테이블이 생기거나, 긴급 구매 카드 연결·재고 품목 WMS 코드·단계당 승인 1건이 빠지면 실패한다."""

import copy
import json
import unittest
from pathlib import Path

from validate_db_design import validate_elb_dsn27

ROOT = Path(__file__).resolve().parents[1]


class ElbTargetTest(unittest.TestCase):
    def setUp(self):
        self.target = json.loads(
            (ROOT / "docs/db/schema-metadata/schema-target.json").read_text(
                encoding="utf-8"
            )
        )

    def test_contract_holds(self):
        self.assertEqual(validate_elb_dsn27(self.target), [])
        self.assertEqual(
            sum(t["name"].startswith("elb.") for t in self.target["tables"]), 11
        )

    def test_rejects_regressions(self):
        d = copy.deepcopy(self.target)
        d["tables"].append({"name": "elb.purchase_order", "columns": []})
        d["constraints"] = [
            c
            for c in d["constraints"]
            if c["table"] not in ("elb.request", "elb.catalog_item", "elb.approval")
            or c["kind"] not in ("CHECK", "UK", "UK_PARTIAL")
            or c["columns"] == ["workspace_id", "generation_id", "id"]
        ]
        errors = validate_elb_dsn27(d)
        for word in ("no POs", "card transaction", "WMS item code", "one decision"):
            self.assertTrue(any(word in e for e in errors), word)


if __name__ == "__main__":
    unittest.main()
