"""DSN-11: ERP 목표 설계 계약 — 재고 원장·고정 계정·원천 중복 전표가 돌아오면 검증이 실패한다."""

import copy
import json
import unittest
from pathlib import Path

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

    # 참고: 과거 DSN 설계 확정 단계에서 수행하던 test_rebuild_from_schema_json_is_identical은
    # W2 단계마다 목표 표들이 schema.json에 선반영되면서 재생성 비교(rebuild_target.build() == target)가
    # 구조적으로 성립하지 않아 분리·제거함 (W2a MES 선반영, W2b WMS 선반영 등).
    # 목표 설계의 무결성은 아래 test_contract_holds, test_rejects_regressions 및
    # validate_db_design.py --schema schema-target.json이 담당한다.

    def test_contract_holds(self):
        self.assertEqual(validate_erp_dsn11(self.target), [])
        self.assertGreaterEqual(  # DSN-31 adds erp.approval_policy/evidence
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
