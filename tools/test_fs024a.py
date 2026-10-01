"""FS-024a: schema.json 반영의 멱등성과 WMS 설계 계약(격리·원천 멱등 키)."""
import copy
import json
import unittest
from pathlib import Path

import apply_fs024a
from audit_schema_isolation import audit
from validate_db_design import validate_wms

ROOT = Path(__file__).resolve().parents[1]


class ApplyTest(unittest.TestCase):
    def setUp(self):
        self.current = json.loads((ROOT/'docs/db/schema-metadata/schema.json').read_text(encoding='utf-8'))

    def test_apply_is_idempotent_and_isolated(self):
        again = copy.deepcopy(self.current)
        self.assertFalse(apply_fs024a.apply(again))
        self.assertEqual(again, self.current)
        self.assertEqual(sum(t['name'].startswith('wms.') for t in self.current['tables']), 11 if self.current.get('task') in {'FS-026a', 'FS-040'} else 6)
        self.assertEqual(audit(self.current), [])
        self.assertEqual(validate_wms(self.current), [])

    def test_cross_schema_fk_is_rejected(self):
        broken = copy.deepcopy(self.current)
        broken['relations'].append(dict(source='wms.stock_move', columns=['workspace_id', 'generation_id', 'item_id'],
                                        target='mes.item', target_columns=['workspace_id', 'generation_id', 'id'],
                                        on_delete='RESTRICT', on_update='RESTRICT', note='금지'))
        self.assertTrue(audit(broken))
        self.assertTrue(any('no FK from wms' in e for e in validate_wms(broken)))

    def test_source_posting_key_is_required(self):
        broken = copy.deepcopy(self.current)
        broken['constraints'] = [c for c in broken['constraints']
                                 if not (c['table'] == 'wms.stock_document' and c['kind'] == 'UK_PARTIAL' and 'source_key' in c['columns'])]
        self.assertTrue(any('one posting per source' in e for e in validate_wms(broken)))


if __name__ == '__main__':
    unittest.main()
