"""GW 부분 이관의 범위·제약 번호 보존·롤백 생성 계약."""

import copy
import json
import unittest
from pathlib import Path

from apply_gw_a import EXCLUDED, RETIRED, apply
from build_migration import build
from validate_db_design import validate_gw_dsn31

ROOT = Path(__file__).resolve().parents[1]


class GwMigrationTests(unittest.TestCase):
    def setUp(self):
        self.target = json.loads(
            (ROOT / "docs/db/schema-metadata/schema-target.json").read_text()
        )
        self.current = json.loads(
            (ROOT / "docs/db/schema-metadata/schema.json").read_text()
        )

    def test_target_gate_still_requires_team_and_erp(self):
        broken = copy.deepcopy(self.target)
        broken["tables"] = [
            t
            for t in broken["tables"]
            if t["name"] not in {"core.workspace_membership", "erp.approval_evidence"}
        ]
        broken["constraints"] = [
            c
            for c in broken["constraints"]
            if c["table"] not in {"core.workspace_membership", "erp.approval_evidence"}
        ]
        errors = validate_gw_dsn31(broken)
        self.assertTrue(any("TEAM" in e for e in errors))
        self.assertTrue(any("ERP owns" in e for e in errors))
        self.assertEqual(validate_gw_dsn31(self.current), [])

    def test_partial_scope_and_idempotency(self):
        self.assertFalse(EXCLUDED & {t["name"] for t in self.current["tables"]})
        self.assertEqual(
            sum(t["name"].startswith("gw.") and not t["name"].startswith("gw.work_") for t in self.current["tables"]), 19
        )
        self.assertFalse(apply(self.current, self.target))
        self.assertEqual(
            sum(c["reason"].startswith(RETIRED) for c in self.current["constraints"]), 2
        )

    def test_fk_and_check_removed_before_columns_on_rollback(self):
        # 독립 최소 명세로 복합FK 삭제가 표 DROP보다 앞서는지 확인한다.
        design = {
            "tables": [
                {
                    "name": "gw.parent",
                    "columns": [{"name": "id", "type": "bigint", "nullable": False}],
                },
                {
                    "name": "gw.child",
                    "columns": [
                        {"name": "id", "type": "bigint", "nullable": False},
                        {"name": "parent_id", "type": "bigint", "nullable": True},
                    ],
                },
            ],
            "constraints": [],
            "relations": [
                {
                    "source": "gw.child",
                    "columns": ["parent_id"],
                    "target": "gw.parent",
                    "target_columns": ["id"],
                    "on_delete": "RESTRICT",
                    "on_update": "RESTRICT",
                }
            ],
        }
        old = {
            "tables": [
                {
                    "name": "gw.child",
                    "columns": [{"name": "id", "type": "bigint", "nullable": False}],
                }
            ],
            "constraints": [],
            "relations": [],
        }
        _, down, _ = build(design, ["gw.*"], None, old)
        self.assertEqual(down[0], "ALTER TABLE gw.child DROP CONSTRAINT r0_fk")
        self.assertLess(
            down.index("ALTER TABLE gw.child DROP COLUMN parent_id"),
            down.index("DROP TABLE gw.parent"),
        )

    def test_unsafe_existing_column_fails(self):
        target = copy.deepcopy(self.target)
        person = next(t for t in target["tables"] if t["name"] == "gw.person")
        person["columns"].append({"name": "unsafe", "nullable": False, "default": None})
        with self.assertRaisesRegex(ValueError, "안전하지 않은"):
            apply(self.current, target)


if __name__ == "__main__":
    unittest.main()
