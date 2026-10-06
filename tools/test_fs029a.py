"""FS-029a: schema.json 반영의 멱등성과 CMMS 설계 계약(격리·가져오기 1건·신호 1건당 작업지시 1건·재고 원장 없음)."""

import copy
import json
import unittest
from pathlib import Path

import apply_fs029a
from audit_schema_isolation import audit
from validate_db_design import expected_names, validate, validate_cmms

ROOT = Path(__file__).resolve().parents[1]


class ApplyTest(unittest.TestCase):
    def setUp(self):
        self.current = json.loads(
            (ROOT / "docs/db/schema-metadata/schema.json").read_text(encoding="utf-8")
        )

    def test_apply_is_idempotent_and_valid(self):
        again = copy.deepcopy(self.current)
        self.assertFalse(apply_fs029a.apply(again))
        self.assertEqual(again, self.current)
        self.assertEqual(
            sum(t["name"].startswith("cmms.") for t in self.current["tables"]), 6
        )
        self.assertEqual(audit(self.current), [])
        self.assertEqual(validate(self.current, expected_names(self.current)), [])

    def test_cross_schema_fk_is_rejected(self):
        broken = copy.deepcopy(self.current)
        broken["relations"].append(
            dict(
                source="cmms.asset",
                columns=["workspace_id", "generation_id", "code"],
                target="mes.equipment",
                target_columns=["workspace_id", "generation_id", "id"],
                on_delete="RESTRICT",
                on_update="RESTRICT",
                note="금지",
            )
        )
        self.assertTrue(audit(broken))
        self.assertTrue(any("no FK from cmms" in e for e in validate_cmms(broken)))

    def test_signal_and_import_uniqueness_are_required(self):
        broken = copy.deepcopy(self.current)
        broken["constraints"] = [
            c
            for c in broken["constraints"]
            if not (c["table"].startswith("cmms.") and c["kind"] == "UK_PARTIAL")
        ]
        errors = validate_cmms(broken)
        self.assertTrue(any("one live work order per signal" in e for e in errors))
        self.assertTrue(any("one asset per imported source code" in e for e in errors))

    def test_no_stock_ledger_and_module_keys(self):
        names = {
            t["name"] for t in self.current["tables"] if t["name"].startswith("cmms.")
        }
        self.assertFalse({n for n in names if "stock" in n})
        for t in ("core.workspace_module", "core.app_review"):
            self.assertTrue(
                any(
                    c["table"] == t
                    and c["kind"] == "CHECK"
                    and "'cmms'" in c["expression"]
                    for c in self.current["constraints"]
                )
            )


if __name__ == "__main__":
    unittest.main()
