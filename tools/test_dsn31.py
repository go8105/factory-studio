"""DSN-31: GW 목표 설계 계약 — GW에 인사·소속 이력·첨부 표가 생기거나, 병렬 결재(단계 순번 유일 키 없음)·알림 중복 0·TEAM core·ERP 확정 통제가 빠지면 실패한다."""

import copy
import json
import unittest
from pathlib import Path

import apply_dsn00
import apply_dsn31
from validate_db_design import validate_gw_dsn31

ROOT = Path(__file__).resolve().parents[1]
S = ["workspace_id", "generation_id"]


class GwTargetTest(unittest.TestCase):
    def setUp(self):
        self.target = json.loads(
            (ROOT / "docs/db/schema-metadata/schema-target.json").read_text(
                encoding="utf-8"
            )
        )

    def test_contract_holds(self):
        self.assertEqual(validate_gw_dsn31(self.target), [])
        self.assertEqual(
            sum(t["name"].startswith("gw.") for t in self.target["tables"]), 24
        )

    def test_demo_implementation_does_not_skip_future_team_design(self):
        current = json.loads((ROOT / "docs/db/schema-metadata/schema.json").read_text())
        target = apply_dsn00.base(copy.deepcopy(current))
        self.assertTrue(apply_dsn31.apply(target))
        names = {t["name"] for t in target["tables"]}
        self.assertIn("core.company", names)
        self.assertIn("hr.work_request", names)
        workspace_checks = [c["expression"] for c in target["constraints"] if c["table"] == "core.workspace" and c["kind"] == "CHECK"]
        self.assertTrue(any("COMPANY" in e and "TEAM" in e for e in workspace_checks))
        self.assertIn("core.workspace_membership", names)
        self.assertIn("gw.document_reader", names)
        self.assertIn("erp.approval_evidence", names)
        person = next(t for t in target["tables"] if t["name"] == "gw.person")
        self.assertIn("hr_employee_code", {c["name"] for c in person["columns"]})
        before = copy.deepcopy(target)
        self.assertFalse(apply_dsn31.apply(target))
        self.assertEqual(target, before)
        self.assertEqual(validate_gw_dsn31(target), [])

    def test_rejects_regressions(self):
        d = copy.deepcopy(self.target)
        d["tables"] += [
            {"name": "gw.person_assignment", "columns": []},
            {"name": "gw.attachment", "columns": []},
        ]
        d["constraints"].append(
            {
                "table": "gw.approval_step",
                "kind": "UK",
                "columns": S + ["document_id", "seq"],
                "expression": "",
                "reason": "",
            }
        )
        d["constraints"] = [
            c
            for c in d["constraints"]
            if not (
                c["table"] == "gw.notification"
                and c["kind"] == "UK"
                and "event_key" in c["columns"]
            )
        ]
        d["relations"].append(
            {
                "source": "gw.person_identity_binding",
                "columns": ["subject_key"],
                "target": "core.app_user",
                "target_columns": ["id"],
            }
        )
        errors = "\n".join(validate_gw_dsn31(d))
        for word in (
            "belong to HR",
            "no attachment",
            "parallel approval",
            "idempotency",
            "no FK to core.app_user",
        ):
            self.assertIn(word, errors)


if __name__ == "__main__":
    unittest.main()
