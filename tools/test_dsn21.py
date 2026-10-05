"""DSN-21: CMMS 목표 설계 계약 — 금형 출처·기준별 PM 주기·점검표 완료 조건이 빠지거나, 신호 출처가 늘거나, 비용·재고가 저장되면 실패한다."""

import copy
import json
import unittest
from pathlib import Path

from validate_db_design import validate_cmms, validate_cmms_dsn21

ROOT = Path(__file__).resolve().parents[1]


class CmmsTargetTest(unittest.TestCase):
    def setUp(self):
        self.target = json.loads(
            (ROOT / "docs/db/schema-metadata/schema-target.json").read_text(
                encoding="utf-8"
            )
        )

    def test_contract_holds(self):
        self.assertEqual(validate_cmms_dsn21(self.target), [])
        self.assertEqual(validate_cmms(self.target), [])
        self.assertEqual(
            sum(t["name"].startswith("cmms.") for t in self.target["tables"]), 12
        )

    def test_rejects_regressions(self):
        d = copy.deepcopy(self.target)
        for x in d["constraints"]:
            if (
                x["table"] == "cmms.work_order"
                and x["expression"]
                == "source IN ('MANUAL', 'BEMS_ALARM', 'SPC_SIGNAL', 'PM_PLAN')"
            ):
                x["expression"] = (
                    "source IN ('MANUAL', 'BEMS_ALARM', 'SPC_SIGNAL', 'PM_PLAN', 'FEMS_ALARM')"
                )
        next(t for t in d["tables"] if t["name"] == "cmms.spare_part")[
            "columns"
        ].append({"name": "stock_qty"})
        d["constraints"] = [
            c for c in d["constraints"] if c["reason"] != "점검표 완료 조건(Q3)"
        ]
        errors = validate_cmms_dsn21(d)
        for word in ("Q4", "Q6", "Q3"):
            self.assertTrue(any(word in e for e in errors), word)


if __name__ == "__main__":
    unittest.main()
