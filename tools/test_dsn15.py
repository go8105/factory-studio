"""DSN-15: FEMS 목표 설계 계약 — 계약전력 없는 TOU·15분 계측 테이블·확정 1건/진행 경보 1건 누락·계수 분리 정책 누락이면 실패한다."""

import copy
import json
import unittest
from pathlib import Path

from validate_db_design import validate_fems_dsn15

ROOT = Path(__file__).resolve().parents[1]


class FemsTargetTest(unittest.TestCase):
    def setUp(self):
        self.target = json.loads(
            (ROOT / "docs/db/schema-metadata/schema-target.json").read_text(
                encoding="utf-8"
            )
        )

    def test_contract_holds(self):
        self.assertEqual(validate_fems_dsn15(self.target), [])
        self.assertEqual(
            sum(t["name"].startswith("fems.") for t in self.target["tables"]), 25
        )

    def test_rejects_regressions(self):
        d = copy.deepcopy(self.target)
        d["tables"].append({"name": "fems.reading_15m", "columns": []})
        d["constraints"] = [
            c
            for c in d["constraints"]
            if not (
                c["table"] in ("fems.alarm", "fems.ghg_inventory")
                and c["kind"] == "UK_PARTIAL"
            )
            and "contract_kw > 0" not in c["expression"]
            and c["reason"] != "환산·배출 계수 분리"
        ]
        errors = validate_fems_dsn15(d)
        for word in (
            "contract power",
            "ghg_inventory",
            "one open alarm",
            "factors stay separate",
            "1-hour",
        ):
            self.assertTrue(any(word in e for e in errors), word)


if __name__ == "__main__":
    unittest.main()
