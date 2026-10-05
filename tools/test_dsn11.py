"""DSN-11: ERP 목표 설계는 다시 만들어도 같고, 재고 원장·고정 계정·원천 중복 전표가 돌아오면 검증이 실패한다."""

import copy
import json
import unittest
from pathlib import Path

import apply_dsn00
import apply_dsn11
from validate_db_design import validate_erp_dsn11

ROOT = Path(__file__).resolve().parents[1]


class ErpTargetTest(unittest.TestCase):
    def setUp(self):
        self.target = json.loads(
            (ROOT / "docs/db/schema-metadata/schema-target.json").read_text(
                encoding="utf-8"
            )
        )

    def test_rebuild_from_schema_json_is_identical(self):
        d = apply_dsn00.base(
            json.loads(
                (ROOT / "docs/db/schema-metadata/schema.json").read_text(
                    encoding="utf-8"
                )
            )
        )
        self.assertTrue(apply_dsn11.apply(d))
        self.assertFalse(apply_dsn11.apply(d))
        self.assertEqual(d, self.target)

    def test_contract_holds(self):
        self.assertEqual(validate_erp_dsn11(self.target), [])
        self.assertEqual(
            sum(t["name"].startswith("erp.") for t in self.target["tables"]), 63
        )

    def test_rejects_regressions(self):
        d = copy.deepcopy(self.target)
        d["tables"].append({"name": "erp.stock_ledger", "columns": []})
        d["constraints"] = [
            c
            for c in d["constraints"]
            if not (c["table"] == "erp.journal_entry" and c["kind"] == "UK_PARTIAL")
        ]
        d["constraints"].append(
            {
                "table": "erp.account",
                "kind": "CHECK",
                "columns": [],
                "expression": "(account_code = 'AR')",
                "reason": "",
            }
        )
        errors = validate_erp_dsn11(d)
        for word in (
            "stock ledgers",
            "one live auto journal",
            "one reversal",
            "fixed 7-account",
        ):
            self.assertTrue(any(word in e for e in errors), word)

    def test_refuses_real_schema(self):
        with self.assertRaises(SystemExit):
            apply_dsn11.apply({"target": False})


if __name__ == "__main__":
    unittest.main()
