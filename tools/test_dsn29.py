"""DSN-29: RWS 목표 설계 계약 — 영상·POP 호출 테이블이 생기거나, CMMS 현장 출동 가져오기·고객사 필수·게시 가이드 1건·주 담당 1명이 빠지면 실패한다."""

import copy
import json
import unittest
from pathlib import Path

from validate_db_design import validate_rws_dsn29

ROOT = Path(__file__).resolve().parents[1]


class RwsTargetTest(unittest.TestCase):
    def setUp(self):
        self.target = json.loads(
            (ROOT / "docs/db/schema-metadata/schema-target.json").read_text(
                encoding="utf-8"
            )
        )

    def test_contract_holds(self):
        self.assertEqual(validate_rws_dsn29(self.target), [])
        self.assertEqual(
            sum(t["name"].startswith("rws.") for t in self.target["tables"]), 12
        )

    def test_rejects_regressions(self):
        d = copy.deepcopy(self.target)
        d["tables"].append({"name": "rws.video_session", "columns": []})
        drop = {
            ("cmms.work_order", "UK_PARTIAL"),
            ("rws.guide", "UK_PARTIAL"),
            ("rws.assignment", "UK_PARTIAL"),
        }
        d["constraints"] = [
            c for c in d["constraints"] if (c["table"], c["kind"]) not in drop
        ]
        errors = validate_rws_dsn29(d)
        for word in (
            "no video",
            "CMMS imports",
            "one published guide",
            "primary expert",
        ):
            self.assertTrue(any(word in e for e in errors), word)


if __name__ == "__main__":
    unittest.main()
