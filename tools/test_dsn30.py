"""DSN-30: HR 목표 설계 계약 — 민감 정보 칸·신고 테이블이 생기거나, 사원 코드 유일·근태 1일 1건·월 확정 1건·실지급 = 지급 − 공제가 빠지면 실패한다."""

import copy
import json
import unittest
from pathlib import Path

from validate_db_design import validate_hr_dsn30

ROOT = Path(__file__).resolve().parents[1]


class HrTargetTest(unittest.TestCase):
    def setUp(self):
        self.target = json.loads(
            (ROOT / "docs/db/schema-metadata/schema-target.json").read_text(
                encoding="utf-8"
            )
        )

    def test_contract_holds(self):
        self.assertEqual(validate_hr_dsn30(self.target), [])
        self.assertEqual(
            sum(t["name"].startswith("hr.") and t["name"] not in {"hr.work_account", "hr.work_policy", "hr.clock_session", "hr.work_request", "hr.work_event", "hr.work_close"} for t in self.target["tables"]), 19
        )

    def test_rejects_regressions(self):
        d = copy.deepcopy(self.target)
        next(t for t in d["tables"] if t["name"] == "hr.employee")["columns"].append(
            {"name": "bank_account"}
        )
        d["tables"].append({"name": "hr.tax_report", "columns": []})
        d["constraints"] = [
            c
            for c in d["constraints"]
            if not (c["table"] == "hr.payroll_run" and c["kind"] == "UK_PARTIAL")
        ]
        errors = validate_hr_dsn30(d)
        for word in ("sensitive", "filing", "payroll run"):
            self.assertTrue(any(word in e for e in errors), word)


if __name__ == "__main__":
    unittest.main()
