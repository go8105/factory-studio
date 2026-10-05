"""DSN-13: WMS 목표 설계 계약 — 완제품 전용 LOT·잔량 저장·스캔 원장이 돌아오거나 피킹/보류 유일성이 빠지면 실패한다."""

import copy
import json
import unittest
from pathlib import Path

import apply_dsn13
from validate_db_design import validate_wms, validate_wms_dsn13

ROOT = Path(__file__).resolve().parents[1]


class WmsTargetTest(unittest.TestCase):
    def setUp(self):
        self.target = json.loads(
            (ROOT / "docs/db/schema-metadata/schema-target.json").read_text(
                encoding="utf-8"
            )
        )

    def test_contract_holds(self):
        self.assertEqual(validate_wms_dsn13(self.target), [])
        self.assertEqual(validate_wms(self.target), [])
        self.assertEqual(
            sum(t["name"].startswith("wms.") for t in self.target["tables"]), 23
        )

    def test_rejects_regressions(self):
        d = copy.deepcopy(self.target)
        d["constraints"].append(
            {
                "table": "wms.item",
                "kind": "CHECK",
                "columns": [],
                "expression": "lot_tracked = (item_class = 'FG')",
                "reason": "",
            }
        )
        next(t for t in d["tables"] if t["name"] == "wms.lot")["columns"].append(
            {"name": "qty", "type": "numeric(18,3)", "nullable": False}
        )
        d["constraints"] = [
            c
            for c in d["constraints"]
            if c["table"] not in ("wms.pick_order", "wms.lot_hold")
            or c["kind"] not in ("UK", "UK_PARTIAL")
        ]
        errors = validate_wms_dsn13(d)
        for word in ("per item (Q3)", "ledger", "one pick", "one active hold"):
            self.assertTrue(any(word in e for e in errors), word)

    def test_fails_loudly_on_missing_rule(self):
        d = {
            "target": True,
            "tables": [{"name": "mes.pop_import", "columns": []}],
            "constraints": [],
        }
        with self.assertRaises(SystemExit):
            apply_dsn13.apply(d)


if __name__ == "__main__":
    unittest.main()
