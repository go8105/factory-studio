"""FS-025a: schema.json 반영의 멱등성과 BEMS 설계 계약(격리·관측 구간 유일·R4 해제)."""
import copy
import json
import unittest
from pathlib import Path

import apply_fs025a
from audit_schema_isolation import audit
from validate_db_design import validate_bems

ROOT = Path(__file__).resolve().parents[1]


class ApplyTest(unittest.TestCase):
    def setUp(self):
        self.current = json.loads((ROOT/'docs/db/schema-metadata/schema.json').read_text(encoding='utf-8'))

    def test_apply_is_idempotent_and_isolated(self):
        again = copy.deepcopy(self.current)
        self.assertFalse(apply_fs025a.apply(again))
        self.assertEqual(again, self.current)
        # 10(FS-025a) + 11(BEMS-1a 보강)
        self.assertEqual(sum(t['name'].startswith('bems.') for t in self.current['tables']), 21)
        self.assertEqual(audit(self.current), [])
        self.assertEqual(validate_bems(self.current), [])

    def test_cross_schema_fk_is_rejected(self):
        broken = copy.deepcopy(self.current)
        broken['relations'].append(dict(source='bems.energy_reading', columns=['workspace_id', 'generation_id', 'meter_id'],
                                        target='fems.meter', target_columns=['workspace_id', 'generation_id', 'id'],
                                        on_delete='RESTRICT', on_update='RESTRICT', note='금지'))
        self.assertTrue(audit(broken))
        self.assertTrue(any('no FK from bems' in e for e in validate_bems(broken)))

    def test_reading_hour_key_is_required(self):
        broken = copy.deepcopy(self.current)
        broken['constraints'] = [c for c in broken['constraints']
                                 if not (c['table'] == 'bems.energy_reading' and c['kind'] == 'UK' and 'period_start' in c['columns'])]
        self.assertTrue(any('one energy reading per meter hour' in e for e in validate_bems(broken)))


if __name__ == '__main__':
    unittest.main()
