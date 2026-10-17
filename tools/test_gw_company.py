"""회사 보안 명세 추가가 기존 운영 제약 번호/복합 참조를 깨지 않는지 검사한다."""

import copy
import json
import unittest
from pathlib import Path

from apply_gw_company import apply
from audit_schema_isolation import audit
from build_migration import build

ROOT = Path(__file__).resolve().parents[1]
SECURITY = {
    "gw." + n
    for n in (
        "collaboration_settings",
        "person_identity_binding",
        "role_grant",
        "document_reader",
        "step_assignment",
    )
}


class CompanySchemaTest(unittest.TestCase):
    def test_partial_security_metadata_is_not_silently_accepted(self):
        with self.assertRaises(ValueError):
            apply({"tables": [{"name": "gw.person_identity_binding"}]})

    def test_adding_company_security_preserves_existing_ddl_and_is_idempotent(self):
        current = json.loads((ROOT / "docs/db/schema-metadata/schema.json").read_text())
        before = copy.deepcopy(current)
        before["tables"] = [t for t in before["tables"] if t["name"] not in SECURITY]
        before["constraints"] = [
            c
            for c in before["constraints"]
            if c["table"] not in SECURITY
            and not (
                c["table"] == "gw.approval_step"
                and c["columns"]
                == ["workspace_id", "generation_id", "document_id", "id"]
            )
        ]
        before["relations"] = [
            r for r in before["relations"] if r["source"] not in SECURITY
        ]
        after = copy.deepcopy(before)
        self.assertTrue(apply(after))
        # Array offsets are the deployed PostgreSQL cN/rN names.
        self.assertEqual(
            after["constraints"][: len(before["constraints"])], before["constraints"]
        )
        self.assertEqual(
            after["relations"][: len(before["relations"])], before["relations"]
        )
        self.assertFalse(apply(after))
        up, down, _ = build(after, ["gw.*"], None, before)
        self.assertFalse(any(s.startswith("DROP ") or " DROP " in s for s in up))
        self.assertTrue(
            any(
                "document_id,step_id" in s and "REFERENCES gw.approval_step" in s
                for s in up
            )
        )
        self.assertEqual(sum(s.startswith("DROP TABLE") for s in down), 5)
        self.assertEqual(audit(after), [])


if __name__ == "__main__":
    unittest.main()
