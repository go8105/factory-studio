"""DSN-17: SPC 목표 설계 계약 — 계수 표가 DB로 오거나, 부분군이 계량/계수를 섞거나, 규칙 1~8·규격 이탈 유일성이 빠지면 실패한다."""

import copy
import json
import unittest
from pathlib import Path

from validate_db_design import validate_spc, validate_spc_dsn17

ROOT = Path(__file__).resolve().parents[1]


class SpcTargetTest(unittest.TestCase):
    def setUp(self):
        self.target = json.loads(
            (ROOT / "docs/db/schema-metadata/schema-target.json").read_text(
                encoding="utf-8"
            )
        )

    def test_contract_holds(self):
        self.assertEqual(validate_spc_dsn17(self.target), [])
        self.assertEqual(validate_spc(self.target), [])
        self.assertEqual(
            sum(t["name"].startswith("spc.") for t in self.target["tables"]), 10
        )

    def test_rejects_regressions(self):
        d = copy.deepcopy(self.target)
        d["tables"].append({"name": "spc.chart_constant", "columns": []})
        d["constraints"] = [
            c
            for c in d["constraints"]
            if not (
                c["table"] == "spc.subgroup" and "inspected_qty > 0" in c["expression"]
            )
            and c["expression"] != "rule BETWEEN 1 AND 8"
            and not (c["table"] == "spc.spec_violation" and c["kind"] == "UK")
        ]
        errors = validate_spc_dsn17(d)
        for word in (
            "constants",
            "variable or attribute",
            "Nelson",
            "one spec violation",
        ):
            self.assertTrue(any(word in e for e in errors), word)


if __name__ == "__main__":
    unittest.main()
