"""DSN-26: SCM 목표 설계 계약 — 실행 테이블(발주·판매계획·재고 이동)이 SCM으로 오거나, 확정 1건·제안 1건·조정 사유가 빠지면 실패한다."""

import copy
import json
import unittest
from pathlib import Path

from validate_db_design import validate_scm_dsn26

ROOT = Path(__file__).resolve().parents[1]


class ScmTargetTest(unittest.TestCase):
    def setUp(self):
        self.target = json.loads(
            (ROOT / "docs/db/schema-metadata/schema-target.json").read_text(
                encoding="utf-8"
            )
        )

    def test_contract_holds(self):
        self.assertEqual(validate_scm_dsn26(self.target), [])
        self.assertEqual(
            sum(t["name"].startswith("scm.") for t in self.target["tables"]), 9
        )

    def test_rejects_regressions(self):
        d = copy.deepcopy(self.target)
        d["tables"].append({"name": "scm.purchase_order", "columns": []})
        d["constraints"] = [
            c
            for c in d["constraints"]
            if not (
                c["table"] in ("scm.forecast_run", "scm.inventory_policy")
                and c["kind"] == "UK_PARTIAL"
            )
            and "adjust_reason" not in c["expression"]
        ]
        errors = validate_scm_dsn26(d)
        for word in (
            "execution stays",
            "one confirmed forecast",
            "one proposed policy",
            "need a reason",
        ):
            self.assertTrue(any(word in e for e in errors), word)


if __name__ == "__main__":
    unittest.main()
