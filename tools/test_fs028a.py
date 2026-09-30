"""FS-028a: schema.json 반영의 멱등성과 SPC 설계 계약(격리·부분군 기록 멱등·부분군 크기 5·측정값 SPC 소유)."""
import copy
import json
import unittest
from pathlib import Path

import apply_fs028a
from audit_schema_isolation import audit
from validate_db_design import design_names, validate, validate_spc

ROOT = Path(__file__).resolve().parents[1]


class ApplyTest(unittest.TestCase):
    def setUp(self):
        self.current = json.loads((ROOT/'docs/db/schema-metadata/schema.json').read_text(encoding='utf-8'))

    def test_apply_is_idempotent_and_valid(self):
        again = copy.deepcopy(self.current)
        self.assertFalse(apply_fs028a.apply(again))
        self.assertEqual(again, self.current)
        self.assertEqual(sum(t['name'].startswith('spc.') for t in self.current['tables']), 5)
        self.assertEqual(audit(self.current), [])
        self.assertEqual(validate(self.current, design_names(self.current['task'])), [])

    def test_cross_schema_fk_is_rejected(self):
        broken = copy.deepcopy(self.current)
        broken['relations'].append(dict(source='spc.subgroup', columns=['workspace_id', 'generation_id', 'characteristic_id'],
                                        target='mes.lot', target_columns=['workspace_id', 'generation_id', 'id'],
                                        on_delete='RESTRICT', on_update='RESTRICT', note='금지'))
        self.assertTrue(audit(broken))
        self.assertTrue(any('no FK from spc' in e for e in validate_spc(broken)))

    def test_subgroup_key_and_fixed_size_are_required(self):
        broken = copy.deepcopy(self.current)
        broken['constraints'] = [c for c in broken['constraints']
                                 if not (c['table'] == 'spc.subgroup' and c['kind'] == 'UK' and 'measured_at' in c['columns'])
                                 and c['expression'] != 'subgroup_size = 5']
        errors = validate_spc(broken)
        self.assertTrue(any('one subgroup per characteristic' in e for e in errors))
        self.assertTrue(any('subgroup size fixed to 5' in e for e in errors))

    def test_measurements_are_not_owned_by_mes(self):
        broken = copy.deepcopy(self.current)
        broken['tables'].append({**broken['tables'][0], 'name': 'mes.measurement'})
        self.assertTrue(any('owned by SPC' in e for e in validate_spc(broken)))

    def test_limit_start_is_timestamp_not_calendar_key(self):
        # effective_from은 달력 문자열 키 규칙 대상이라 한계 적용 시각은 effective_at으로 둔다.
        columns = {c['name'] for t in self.current['tables'] if t['name'] == 'spc.control_limit' for c in t['columns']}
        self.assertIn('effective_at', columns)
        self.assertNotIn('effective_from', columns)


if __name__ == '__main__':
    unittest.main()
