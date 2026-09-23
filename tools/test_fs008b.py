"""Metadata regression and file-safety tests, no DB/service execution."""
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import apply_fs008b as apply
from validate_db_design import validate, design_names

ROOT=Path(__file__).resolve().parents[1]
BACKUP=ROOT/'docs/db/schema-metadata/backups'

class FS008b(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        candidates=list(BACKUP.glob('schema.before-FS-008b.*.json'))
        cls.raw=(candidates[0] if candidates else ROOT/'docs/db/schema-metadata/schema.json').read_bytes()
        cls.before=json.loads(cls.raw)
        cls.after=apply.transform(cls.before)
    def errors(self,d):return validate(d,design_names('FS-008b'))
    def test_inventory_and_column_delta(self):
        self.assertFalse(self.errors(self.after))
        self.assertEqual(apply.counts(self.after),apply.AFTER)
        self.assertEqual(sum(len(t['columns']) for t in self.after['tables']),712)
        b={t['name']:t for t in self.before['tables']};a={t['name']:t for t in self.after['tables']}
        for name in ['fems.meter','fems.meter_channel','fems.energy_reading']:
            self.assertEqual(len(a[name]['columns']),len(b[name]['columns'])-1)
    def test_no_input_mutation(self):self.assertEqual(self.before,json.loads(self.raw))
    def test_unit_fk_cannot_be_weakened(self):
        for source in ['fems.energy_reading','fems.energy_allocation']:
            d=copy.deepcopy(self.after)
            r=next(r for r in d['relations'] if r['source']==source and r['target']=='fems.meter_channel')
            r['columns'].remove('unit');r['target_columns'].remove('unit')
            self.assertTrue(self.errors(d))
    def test_target_unique_is_required(self):
        d=copy.deepcopy(self.after)
        d['constraints']=[c for c in d['constraints'] if not(c['table']=='fems.meter_channel' and c['kind']=='UK' and c['columns']==apply.S+['id','unit'])]
        self.assertTrue(self.errors(d))
    def test_null_due_is_required(self):
        for table,column in [('erp.partner','payment_term_days'),('erp.receivable','due_date'),('erp.payable','due_date'),('erp.purchase_invoice','due_date')]:
            d=copy.deepcopy(self.after)
            next(c for t in d['tables'] if t['name']==table for c in t['columns'] if c['name']==column)['nullable']=False
            self.assertTrue(self.errors(d))
    def test_unchanged_business_tables(self):
        changed={'core.dashboard_layout','erp.item','erp.partner','erp.receivable','erp.payable','erp.purchase_invoice','fems.energy_allocation','fems.energy_reading','fems.meter','fems.meter_channel'}
        self.assertEqual([t for t in self.before['tables'] if t['name'] not in changed],[t for t in self.after['tables'] if t['name'] not in changed])
    def run_cli(self,path,*args):
        return subprocess.run([sys.executable,str(ROOT/'tools/apply_fs008b.py'),'--schema',str(path),*args],capture_output=True,text=True)
    def test_check_backup_and_idempotence(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'schema.json';p.write_bytes(self.raw);stamp=p.stat().st_mtime_ns
            self.assertEqual(self.run_cli(p,'--check').returncode,0)
            self.assertEqual(p.read_bytes(),self.raw);self.assertEqual(p.stat().st_mtime_ns,stamp)
            self.assertFalse((p.parent/'backups').exists())
            self.assertEqual(self.run_cli(p).returncode,0)
            b=p.parent/'backups'/f'schema.before-FS-008b.{hashlib.sha256(self.raw).hexdigest()}.json'
            self.assertEqual(b.read_bytes(),self.raw)
            result=p.read_bytes();stamp=p.stat().st_mtime_ns
            self.assertEqual(self.run_cli(p).returncode,0)
            self.assertEqual(p.read_bytes(),result);self.assertEqual(p.stat().st_mtime_ns,stamp)
    def test_invalid_source_aborts_without_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'schema.json';d=copy.deepcopy(self.before);d['migration_revision']='applied';p.write_text(json.dumps(d));raw=p.read_bytes()
            self.assertNotEqual(self.run_cli(p).returncode,0)
            self.assertEqual(p.read_bytes(),raw);self.assertFalse((p.parent/'backups').exists())
    def test_applied_invalid_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'schema.json';d=copy.deepcopy(self.after);d['tables'].pop();p.write_text(json.dumps(d));raw=p.read_bytes()
            self.assertNotEqual(self.run_cli(p).returncode,0);self.assertEqual(p.read_bytes(),raw)
    def test_atomic_replace_failure_preserves_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'schema.json';p.write_bytes(self.raw)
            with patch.object(sys,'argv',['apply_fs008b','--schema',str(p)]),patch.object(apply.os,'replace',side_effect=OSError('injected replace failure')):
                self.assertEqual(apply.main(),1)
            self.assertEqual(p.read_bytes(),self.raw);self.assertFalse(list(p.parent.glob('.fs008b-*')))
    def test_missing_policy_rejected(self):
        d=copy.deepcopy(self.after);d['constraints']=[c for c in d['constraints'] if c['reason']!='FS-008b 매입 만기 우선순위']
        self.assertTrue(self.errors(d))

if __name__=='__main__':unittest.main()
