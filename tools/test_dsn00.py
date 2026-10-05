"""DSN-00: 목표 설계 파일이 기존 검사를 모두 켠 채 검증되고, 실제 DB 기록·낡은 기준·문서 없는 새 테이블을 거부한다."""

import copy
import json
import unittest
from pathlib import Path

from audit_schema_isolation import audit
from schema_ddl import ddl
from validate_db_design import (
    design_names,
    gate_task,
    target_names,
    validate,
    validate_target,
)

ROOT = Path(__file__).resolve().parents[1]


class TargetTest(unittest.TestCase):
    def setUp(self):
        self.target = json.loads(
            (ROOT / "docs/db/schema-metadata/schema-target.json").read_text(
                encoding="utf-8"
            )
        )
        self.expected = design_names(gate_task(self.target)) | target_names()

    def test_target_passes_with_every_existing_check(self):
        self.assertEqual(gate_task(self.target), json.loads((ROOT / "docs/db/schema-metadata/schema.json").read_text(encoding="utf-8"))["task"])
        self.assertEqual(
            validate(self.target, self.expected) + validate_target(self.target), []
        )

    def test_rejects_db_record_and_stale_base(self):
        d = copy.deepcopy(self.target)
        d.update(migration_revision="fs999", base_task="FS-028a")
        self.assertEqual(len(validate_target(d)), 2)

    def test_gate_keeps_checks_on(self):
        d = copy.deepcopy(self.target)
        d["constraints"] = [
            c
            for c in d["constraints"]
            if not (c["table"] == "cmms.work_order" and c["kind"] == "UK_PARTIAL")
        ]
        self.assertTrue(validate(d, self.expected))

    def test_new_table_needs_design_doc_and_scope(self):
        d = copy.deepcopy(self.target)
        fake = copy.deepcopy(
            next(t for t in d["tables"] if t["name"] == "core.app_user")
        )
        fake.update(name="zz_fixture.undocumented", scope="generation")
        d["tables"].append(fake)
        self.assertTrue(
            any("Design inventory mismatch" in e for e in validate(d, self.expected))
        )
        self.assertIn("R5: missing/non-required scope key in zz_fixture.undocumented", audit(d))

    def test_ddl_covers_every_object(self):
        sql = ddl(self.target)
        self.assertEqual(
            sum(s.startswith("CREATE TABLE") for s in sql), len(self.target["tables"])
        )
        self.assertEqual(
            sum("FOREIGN KEY" in s for s in sql), len(self.target["relations"])
        )


if __name__ == "__main__":
    unittest.main()
