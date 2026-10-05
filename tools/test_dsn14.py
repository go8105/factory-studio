"""DSN-14: QMS 목표 설계 계약 — AQL 표가 DB로 들어오거나, 공정 검사가 QMS로 오거나, CAPA·Ac/Re가 빠지면 실패한다."""

import copy
import json
import unittest
from pathlib import Path

from validate_db_design import validate_qms, validate_qms_dsn14

ROOT = Path(__file__).resolve().parents[1]


class QmsTargetTest(unittest.TestCase):
    def setUp(self):
        self.target = json.loads(
            (ROOT / "docs/db/schema-metadata/schema-target.json").read_text(
                encoding="utf-8"
            )
        )

    def test_contract_holds(self):
        self.assertEqual(validate_qms_dsn14(self.target), [])
        self.assertEqual(validate_qms(self.target), [])
        self.assertEqual(
            sum(t["name"].startswith("qms.") for t in self.target["tables"]), 15
        )

    def test_rejects_regressions(self):
        d = copy.deepcopy(self.target)
        d["tables"] += [
            {"name": "qms.aql_table", "columns": []},
            {"name": "qms.process_inspection", "columns": []},
        ]
        d["relations"] = [r for r in d["relations"] if r["source"] != "qms.capa"]
        d["constraints"] = [
            c
            for c in d["constraints"]
            if "reject_number = accept_number + 1" not in c["expression"]
        ]
        errors = validate_qms_dsn14(d)
        for word in ("AQL table", "MES Q5", "CAPA", "Ac/Re"):
            self.assertTrue(any(word in e for e in errors), word)


if __name__ == "__main__":
    unittest.main()
