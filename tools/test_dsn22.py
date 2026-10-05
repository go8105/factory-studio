"""DSN-22: POP 목표 설계 계약 — POP가 다른 업무 스키마로 FK를 걸거나, MES·WMS 가져오기 종류가 POP와 어긋나거나, 입력 번호·모듈 키가 빠지면 실패한다."""

import copy
import json
import unittest
from pathlib import Path

from validate_db_design import validate_pop_dsn22

ROOT = Path(__file__).resolve().parents[1]


class PopTargetTest(unittest.TestCase):
    def setUp(self):
        self.target = json.loads(
            (ROOT / "docs/db/schema-metadata/schema-target.json").read_text(
                encoding="utf-8"
            )
        )

    def test_contract_holds(self):
        self.assertEqual(validate_pop_dsn22(self.target), [])
        self.assertEqual(
            sum(t["name"].startswith("pop.") for t in self.target["tables"]), 7
        )

    def test_rejects_regressions(self):
        d = copy.deepcopy(self.target)
        d["relations"].append(
            {
                "source": "pop.entry",
                "target": "mes.lot",
                "columns": [],
                "target_columns": [],
            }
        )
        for x in d["constraints"]:
            if x["table"] == "mes.pop_import" and "entry_kind IN" in x["expression"]:
                x["expression"] = x["expression"].replace(", 'INSPECT'", "")
        d["constraints"] = [
            c
            for c in d["constraints"]
            if not (
                c["table"] == "pop.entry"
                and c["kind"] == "UK"
                and c["columns"][-1] == "entry_no"
            )
        ]
        errors = validate_pop_dsn22(d)
        for word in ("pop/core", "mes.pop_import kinds", "entry_no unique"):
            self.assertTrue(any(word in e for e in errors), word)


if __name__ == "__main__":
    unittest.main()
