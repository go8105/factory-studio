"""GW metadata invariants and safe additive application."""
import copy
import json
import unittest
from pathlib import Path

import apply_fs030a
from validate_db_design import expected_names, validate
from validate_fs030a import validate_gw


class GWMetadataTest(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((Path(__file__).resolve().parents[1]/'docs/db/schema-metadata/schema.json').read_text())

    def test_idempotent_and_all_validators_remain_enabled(self):
        again=copy.deepcopy(self.data)
        self.assertFalse(apply_fs030a.apply(again))
        self.assertEqual(again,self.data)
        self.assertEqual(validate(again, expected_names(again)),[])
        again['constraints']=[c for c in again['constraints'] if c['expression']!='subgroup_size = 5']
        self.assertTrue(any('subgroup size fixed' in e for e in validate(again)))

    def test_additive_reapplication_preserves_existing_rules(self):
        base=copy.deepcopy(self.data)
        for key,field in [('tables','name'),('constraints','table'),('relations','source'),('states','table')]:
            base[key]=[x for x in base[key] if not x[field].startswith('gw.')]
        previous=copy.deepcopy(base)
        self.assertTrue(apply_fs030a.apply(base))
        self.assertEqual(base['tables'][:len(previous['tables'])],previous['tables'])
        self.assertTrue(any(t['name']=='core.app_review' for t in base['tables']))
        self.assertEqual(validate_gw(base),[])

    def test_partial_install_is_not_silently_accepted(self):
        self.data['tables']=[t for t in self.data['tables'] if t['name']!='gw.board_event']
        with self.assertRaises(ValueError):
            apply_fs030a.apply(self.data)

    def test_later_gw_extension_is_preserved_on_reapplication(self):
        extended=copy.deepcopy(self.data)
        extended['tables'].append(dict(name='gw.future_extension',columns=[]))
        before=copy.deepcopy(extended)
        self.assertFalse(apply_fs030a.apply(extended))
        self.assertEqual(extended,before)

    def test_missing_active_source_key_is_rejected(self):
        self.data['constraints']=[c for c in self.data['constraints'] if not(c['table']=='gw.approval_document' and c['kind']=='UK_PARTIAL')]
        self.assertIn('FS-030: one active source approval',validate_gw(self.data))

    def test_cross_scope_reference_is_rejected(self):
        self.data['relations'].append(dict(source='gw.approval_document',columns=['workspace_id','generation_id','drafter_id'],target='erp.partner',target_columns=['workspace_id','generation_id','id'],on_delete='RESTRICT',on_update='RESTRICT',note='invalid'))
        self.assertTrue(validate_gw(self.data))

    def test_missing_module_and_clock_are_rejected(self):
        for c in self.data['constraints']:
            if c['table']=='core.workspace_module': c['expression']=c['expression'].replace(", 'gw'",'')
        for t in self.data['tables']:
            if t['name']=='gw.person':
                for c in t['columns']:
                    if c['name']=='created_at': c['default']='now()'
        errors=validate_gw(self.data)
        self.assertIn('FS-030: core.workspace_module GW module key',errors)
        self.assertIn('FS-030: gw.person database clock',errors)


if __name__=='__main__': unittest.main()
