"""FS-008c bounded regression tests; no DDL or service execution."""
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import apply_fs008c as apply
from validate_db_design import validate, design_names

ROOT=Path(__file__).resolve().parents[1]
SOURCE_SHA='213415b5f1e6b44feaceaffc9366bbe449d33d0f484c1e1d9ea8992637831110'

class FS008c(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path=ROOT/f'docs/db/schema-metadata/backups/schema.before-FS-008c.{SOURCE_SHA}.json'
        if not path.exists():path=ROOT/'docs/db/schema-metadata/schema.json'
        cls.raw=path.read_bytes()
        assert hashlib.sha256(cls.raw).hexdigest()==SOURCE_SHA
        cls.before=json.loads(cls.raw)
        cls.after=apply.transform(cls.before)
    def cli(self,p,*args):
        return subprocess.run([sys.executable,str(ROOT/'tools/apply_fs008c.py'),'--schema',str(p),*args],capture_output=True,text=True)
    def test_only_two_constraints_removed(self):
        expected=copy.deepcopy(self.before)
        expected['constraints']=[c for c in expected['constraints'] if not(c['table']=='fems.meter' and c['kind']=='CHECK' and c['expression'] in {apply.DA,apply.DB_OLD})]
        expected.update(version='0.9.1',task='FS-008c',date='2026-09-23')
        expected['change_log'].append(self.after['change_log'][-1])
        self.assertEqual(self.after,expected)
        self.assertEqual(len(self.after['constraints']),526)
        self.assertEqual(self.before,json.loads(self.raw))
    def test_defects_absent(self):
        expressions=[c['expression'] for c in apply.checks(self.after)]
        self.assertNotIn(apply.DA,expressions);self.assertNotIn(apply.DB_OLD,expressions)
        self.assertEqual(expressions.count(apply.DB_KEEP),1)
    def test_channel_unchanged(self):
        for key in ['tables','constraints','relations','states','code_lists']:
            before=[x for x in self.before[key] if 'fems.meter_channel' in json.dumps(x)]
            after=[x for x in self.after[key] if 'fems.meter_channel' in json.dumps(x)]
            self.assertEqual(before,after)
    def test_transform_idempotence(self):self.assertEqual(apply.transform(self.after),self.after)
    def test_new_task_retains_existing_validation(self):
        self.assertEqual(design_names('FS-008c'),design_names('FS-008b'))
        self.assertFalse(validate(self.after,design_names('FS-008c')))
        d=copy.deepcopy(self.after)
        d['constraints']=[c for c in d['constraints'] if c['reason']!='소명 양쪽 합계 한도']
        self.assertTrue(validate(d,design_names('FS-008c')))
    def test_check_backup_and_file_idempotence(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'schema.json';p.write_bytes(self.raw);stamp=p.stat().st_mtime_ns
            self.assertEqual(self.cli(p,'--check').returncode,0)
            self.assertEqual(p.read_bytes(),self.raw);self.assertEqual(p.stat().st_mtime_ns,stamp)
            self.assertFalse((p.parent/'backups').exists())
            self.assertEqual(self.cli(p).returncode,0)
            backup=p.parent/'backups'/f'schema.before-FS-008c.{SOURCE_SHA}.json'
            self.assertEqual(backup.read_bytes(),self.raw)
            result=p.read_bytes();stamp=p.stat().st_mtime_ns
            for args in [(),('--check',)]:
                self.assertEqual(self.cli(p,*args).returncode,0)
                self.assertEqual(p.read_bytes(),result);self.assertEqual(p.stat().st_mtime_ns,stamp)
            self.assertEqual(len(list(backup.parent.iterdir())),1)
    def test_invalid_input_preserves_source(self):
        for field,value in [('version','0.8.0'),('migration_revision','applied')]:
            with tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp)/'schema.json';d=copy.deepcopy(self.before);d[field]=value;p.write_text(json.dumps(d));raw=p.read_bytes()
                self.assertNotEqual(self.cli(p).returncode,0)
                self.assertEqual(p.read_bytes(),raw);self.assertFalse((p.parent/'backups').exists())
    def test_partial_input_rejected(self):
        d=copy.deepcopy(self.before);d['constraints']=[c for c in d['constraints'] if c['expression']!=apply.DA]
        with self.assertRaises(ValueError):apply.transform(d)
    def test_invalid_applied_state_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'schema.json';d=copy.deepcopy(self.after)
            next(c for c in apply.checks(d) if c['expression']==apply.DB_KEEP)['expression']=apply.DB_OLD
            p.write_text(json.dumps(d));raw=p.read_bytes()
            self.assertNotEqual(self.cli(p).returncode,0);self.assertEqual(p.read_bytes(),raw)
    def test_atomic_failure_preserves_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'schema.json';p.write_bytes(self.raw)
            with patch.object(sys,'argv',['apply_fs008c','--schema',str(p)]),patch.object(apply.os,'replace',side_effect=OSError('injected replace failure')):
                self.assertEqual(apply.main(),1)
            self.assertEqual(p.read_bytes(),self.raw)
            self.assertEqual(next((p.parent/'backups').iterdir()).read_bytes(),self.raw)
            self.assertFalse(list(p.parent.glob('.fs008c-*')))
    def test_backup_collision_preserves_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'schema.json';p.write_bytes(self.raw)
            backup=p.parent/'backups'/f'schema.before-FS-008c.{SOURCE_SHA}.json';backup.parent.mkdir();backup.write_bytes(b'wrong backup')
            self.assertNotEqual(self.cli(p).returncode,0);self.assertEqual(p.read_bytes(),self.raw)
            self.assertEqual(backup.read_bytes(),b'wrong backup')

if __name__=='__main__':unittest.main()
