"""DSN-90: 통합 계약 — 흐름의 받는 쪽 원천 번호 칸·가져오기 멱등 UK·원천 종류 값이 빠지면 실패한다."""

import copy
import json
import unittest
from pathlib import Path

from validate_db_design import validate_integration_dsn90

ROOT = Path(__file__).resolve().parents[1]


class IntegrationTargetTest(unittest.TestCase):
    def setUp(self):
        self.target = json.loads(
            (ROOT / "docs/db/schema-metadata/schema-target.json").read_text(
                encoding="utf-8"
            )
        )

    def test_contract_holds(self):
        self.assertEqual(validate_integration_dsn90(self.target), [])

    def test_rejects_regressions(self):
        d = copy.deepcopy(self.target)
        partner = next(t for t in d["tables"] if t["name"] == "erp.partner")
        partner["columns"] = [
            c for c in partner["columns"] if c["name"] != "crm_account_code"
        ]
        d["constraints"] = [
            c
            for c in d["constraints"]
            if not (c["table"] == "mes.pop_import" and c["kind"] == "UK")
        ]
        for c in d["constraints"]:
            if c["table"] == "erp.purchase_invoice" and c["kind"] == "CHECK":
                c["expression"] = c["expression"].replace(", 'FREIGHT'", "")
        errors = "\n".join(validate_integration_dsn90(d))
        for word in (
            "erp.partner.crm_account_code missing",
            "mes.pop_import.pop_entry_ref needs a unique key",
            "'FREIGHT' missing",
        ):
            self.assertIn(word, errors)


if __name__ == "__main__":
    unittest.main()
