"""DSN-16: BEMS 목표 설계 계약 — 휴일 달력 중복·core.holiday FK·승인 없는 피크 제어·스케줄 대상 둘이면 실패한다."""

import copy
import json
import unittest
from pathlib import Path

from validate_db_design import validate_bems, validate_bems_dsn16

ROOT = Path(__file__).resolve().parents[1]


class BemsTargetTest(unittest.TestCase):
    def setUp(self):
        self.target = json.loads(
            (ROOT / "docs/db/schema-metadata/schema-target.json").read_text(
                encoding="utf-8"
            )
        )

    def test_contract_holds(self):
        self.assertEqual(validate_bems_dsn16(self.target), [])
        self.assertEqual(validate_bems(self.target), [])
        self.assertEqual(
            sum(t["name"].startswith("bems.") for t in self.target["tables"]), 21
        )

    def test_rejects_regressions(self):
        d = copy.deepcopy(self.target)
        d["tables"].append({"name": "bems.holiday", "columns": []})
        d["relations"].append(
            {
                "source": "bems.schedule_slot",
                "target": "core.holiday",
                "columns": [],
                "target_columns": [],
            }
        )
        d["constraints"] = [
            c
            for c in d["constraints"]
            if c["reason"] != "피크 감축 승인(Q2)"
            and "(hvac_unit_id IS NULL) <> (lighting_circuit_id IS NULL)"
            not in c["expression"]
        ]
        errors = validate_bems_dsn16(d)
        for word in ("one shared holiday", "no FK", "approval", "exactly one device"):
            self.assertTrue(any(word in e for e in errors), word)


if __name__ == "__main__":
    unittest.main()
