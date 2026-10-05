"""DSN-23: TMS 목표 설계 계약 — ERP·WMS로 FK를 걸거나, 출하지시당 배송 1건·운송사 정산 1건·용차 운송사 규칙이 빠지면 실패한다."""

import copy
import json
import unittest
from pathlib import Path

from validate_db_design import validate_tms_dsn23

ROOT = Path(__file__).resolve().parents[1]


class TmsTargetTest(unittest.TestCase):
    def setUp(self):
        self.target = json.loads(
            (ROOT / "docs/db/schema-metadata/schema-target.json").read_text(
                encoding="utf-8"
            )
        )

    def test_contract_holds(self):
        self.assertEqual(validate_tms_dsn23(self.target), [])
        self.assertEqual(
            sum(t["name"].startswith("tms.") for t in self.target["tables"]), 10
        )

    def test_rejects_regressions(self):
        d = copy.deepcopy(self.target)
        d["relations"].append(
            {
                "source": "tms.dispatch_stop",
                "target": "erp.shipment_order",
                "columns": [],
                "target_columns": [],
            }
        )
        d["constraints"] = [
            c
            for c in d["constraints"]
            if not (
                c["table"] in ("tms.dispatch_stop", "tms.settlement")
                and c["kind"] == "UK_PARTIAL"
            )
        ]
        errors = validate_tms_dsn23(d)
        for word in ("tms/core", "one live delivery", "one confirmed settlement"):
            self.assertTrue(any(word in e for e in errors), word)


if __name__ == "__main__":
    unittest.main()
