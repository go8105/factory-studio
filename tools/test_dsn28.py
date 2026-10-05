"""DSN-28: EIP 목표 설계 계약 — EIP 공지 테이블·KPI 실적 저장·core 대시보드 배치가 생기거나, 사람 연결 HR 코드·확정 보고서 1건이 빠지거나, EIP가 끌 수 있는 모듈 키가 되면 실패한다."""

import copy
import json
import unittest
from pathlib import Path

from validate_db_design import validate_eip_dsn28

ROOT = Path(__file__).resolve().parents[1]


class EipTargetTest(unittest.TestCase):
    def setUp(self):
        self.target = json.loads(
            (ROOT / "docs/db/schema-metadata/schema-target.json").read_text(
                encoding="utf-8"
            )
        )

    def test_contract_holds(self):
        self.assertEqual(validate_eip_dsn28(self.target), [])
        self.assertEqual(
            sum(t["name"].startswith("eip.") for t in self.target["tables"]), 8
        )

    def test_rejects_regressions(self):
        d = copy.deepcopy(self.target)
        d["tables"] += [
            {"name": "eip.notice", "columns": []},
            {"name": "core.dashboard_layout", "columns": []},
        ]
        next(t for t in d["tables"] if t["name"] == "gw.person")["columns"] = [
            {"name": "code"}
        ]
        d["constraints"] = [
            c
            for c in d["constraints"]
            if not (c["table"] == "eip.management_report" and c["kind"] == "UK_PARTIAL")
        ]
        wm = next(
            c
            for c in d["constraints"]
            if c["table"] == "core.workspace_module"
            and c["kind"] == "CHECK"
            and "module_key IN" in c["expression"]
        )
        wm["expression"] = wm["expression"].rstrip(")") + ", 'eip')"
        errors = validate_eip_dsn28(d)
        for word in (
            "notices belong to GW",
            "HR employee code",
            "not core",
            "one confirmed management report",
        ):
            self.assertTrue(any(word in e for e in errors), word)


if __name__ == "__main__":
    unittest.main()
