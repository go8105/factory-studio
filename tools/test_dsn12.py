"""DSN-12: MES 목표 설계 계약 — 스캔 원장·재고 테이블이 MES로 들어오거나 POP 가져오기 멱등·유효 라벨 1건이 빠지면 실패한다."""

import copy
import json
import unittest
from pathlib import Path

import apply_dsn12
from validate_db_design import validate_mes_dsn12, validate_screen_gaps

ROOT = Path(__file__).resolve().parents[1]


class MesTargetTest(unittest.TestCase):
    def setUp(self):
        self.target = json.loads(
            (ROOT / "docs/db/schema-metadata/schema-target.json").read_text(
                encoding="utf-8"
            )
        )

    def test_contract_holds(self):
        self.assertEqual(validate_mes_dsn12(self.target), [])
        self.assertEqual(
            sum(t["name"].startswith("mes.") for t in self.target["tables"]), 45
        )
        self.assertEqual(validate_screen_gaps(self.target), [])

    def test_rejects_regressions(self):
        d = copy.deepcopy(self.target)
        d["tables"].append({"name": "mes.scan_log", "columns": []})
        d["constraints"] = [
            c
            for c in d["constraints"]
            if c["table"] not in ("mes.pop_import", "mes.label_print")
            or c["kind"] not in ("UK", "UK_PARTIAL")
        ]
        errors = validate_mes_dsn12(d)
        for word in ("POP (Q1)", "idempotent", "one valid label"):
            self.assertTrue(any(word in e for e in errors), word)

    def test_needs_dsn11_first(self):
        with self.assertRaises(SystemExit):
            apply_dsn12.apply({"target": True, "tables": []})


if __name__ == "__main__":
    unittest.main()
