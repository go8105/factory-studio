"""DSN-24: PLM 목표 설계 계약 — ECO 없는 배포·배포 리비전 둘·파일 저장·M-BOM/공정 테이블·다른 스키마 FK가 들어오면 실패한다."""

import copy
import json
import unittest
from pathlib import Path

from validate_db_design import validate_plm_dsn24

ROOT = Path(__file__).resolve().parents[1]


class PlmTargetTest(unittest.TestCase):
    def setUp(self):
        self.target = json.loads(
            (ROOT / "docs/db/schema-metadata/schema-target.json").read_text(
                encoding="utf-8"
            )
        )

    def test_contract_holds(self):
        self.assertEqual(validate_plm_dsn24(self.target), [])
        self.assertEqual(
            sum(t["name"].startswith("plm.") for t in self.target["tables"]), 16
        )

    def test_rejects_regressions(self):
        d = copy.deepcopy(self.target)
        d["tables"].append(
            {"name": "plm.mbom_line", "columns": [{"name": "file_path"}]}
        )
        d["relations"].append(
            {
                "source": "plm.part",
                "target": "mes.item",
                "columns": [],
                "target_columns": [],
            }
        )
        d["constraints"] = [
            c
            for c in d["constraints"]
            if not (
                c["table"] == "plm.part_revision"
                and (
                    "eco_id IS NOT NULL" in c["expression"] or c["kind"] == "UK_PARTIAL"
                )
            )
        ]
        errors = validate_plm_dsn24(d)
        for word in (
            "only through ECO",
            "one current released",
            "no file storage",
            "MES (Q4)",
            "plm/core",
        ):
            self.assertTrue(any(word in e for e in errors), word)


if __name__ == "__main__":
    unittest.main()
