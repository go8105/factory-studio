"""FS-014b metadata/atomic-write regression. No database or product execution."""
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from apply_fs014b import transform, counts, AFTER, main
from validate_db_design import validate, design_names
from audit_schema_isolation import audit

ROOT=Path(__file__).resolve().parents[1]
HASH='98d2f505f5620f025019b152b2e3c018b41e5ddbd5c0bb21cd710a6be1423b25'
FIXTURE=ROOT/f'docs/db/schema-metadata/backups/schema.before-FS-014b.{HASH}.json'


class AccountingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=(FIXTURE if FIXTURE.exists() else ROOT/'docs/db/schema-metadata/schema.json').read_bytes()
        assert hashlib.sha256(cls.raw).hexdigest()==HASH
        cls.original=json.loads(cls.raw)
        cls.result=transform(cls.original)

    def valid(self,d):
        return validate(d,design_names('FS-014b'))

    def run_apply(self,p,*args):
        return subprocess.run([sys.executable,str(ROOT/'tools/apply_fs014b.py'),'--schema',str(p),*args],capture_output=True,text=True)

    def test_inventory_and_input_preservation(self):
        self.assertEqual(counts(self.result),AFTER)
        self.assertEqual(len(self.result['tables']),72)
        self.assertEqual(self.original,json.loads(self.raw))
        self.assertEqual(self.valid(self.result),[])
        self.assertEqual(audit(self.result),[])
        # Non-ERP definitions must remain unchanged.
        for section in ['tables','constraints','relations','states','code_lists']:
            key={'tables':'name','constraints':'table','relations':'source','states':'table','code_lists':'target'}[section]
            before=[v for v in self.original[section] if not v[key].startswith('erp.')]
            after=[v for v in self.result[section] if not v[key].startswith('erp.')]
            self.assertEqual(before,after)

    def test_balance_status_and_cancel_flags_rejected(self):
        for table,field in [('erp.receivable','balance'),('erp.payable','status'),('erp.receipt_apply','cancelled_at'),('erp.payment_apply','status')]:
            with self.subTest(table=table,field=field):
                d=copy.deepcopy(self.result)
                next(t for t in d['tables'] if t['name']==table)['columns'].append(dict(name=field,label='invalid',type='varchar(20)',nullable=True,default=None,rule=''))
                self.assertTrue(self.valid(d))

    def test_cross_schema_and_nullable_scope_rejected(self):
        for mutation in [lambda d:d['relations'].append(dict(source='erp.receipt',target='mes.item',columns=['workspace_id','generation_id','id'],target_columns=['workspace_id','generation_id','id'],on_delete='RESTRICT',on_update='RESTRICT',note='bad')),
                         lambda d:next(c for t in d['tables'] if t['name']=='erp.account' for c in t['columns'] if c['name']=='generation_id').update(nullable=True)]:
            d=copy.deepcopy(self.result);mutation(d);self.assertTrue(self.valid(d))

    def test_aggregate_cannot_be_reclassified_as_check(self):
        d=copy.deepcopy(self.result)
        c=next(c for c in d['constraints'] if c['table']=='erp.receipt_apply' and c['reason']=='소명 양쪽 합계 한도')
        c.update(kind='CHECK',expression='SUM(amount) <= 100')
        self.assertTrue(self.valid(d))

    def test_missing_cancellation_or_limit_policies_rejected(self):
        for reason in ['매출 취소 계약','채무 파생 생성 및 매입 취소','소명 양쪽 합계 한도','소명 물리 삭제 및 감사','회계 잠금 순서','소명 재요청 중복 차단']:
            d=copy.deepcopy(self.result);d['constraints']=[c for c in d['constraints'] if c['reason']!=reason]
            self.assertTrue(self.valid(d),reason)

    def test_missing_source_uniqueness_and_party_fk_rejected(self):
        d=copy.deepcopy(self.result)
        d['constraints']=[c for c in d['constraints'] if not(c['table']=='erp.receivable' and c['kind']=='UK' and c['columns']==['workspace_id','generation_id','sales_record_id'])]
        self.assertTrue(self.valid(d))
        d=copy.deepcopy(self.result)
        d['relations']=[r for r in d['relations'] if not(r['source']=='erp.payment_apply' and r['target']=='erp.payment')]
        self.assertTrue(self.valid(d))

    def test_tax_cardinality_and_two_states(self):
        d=copy.deepcopy(self.result)
        d['constraints']=[c for c in d['constraints'] if not(c['table']=='erp.tax_invoice' and c['kind']=='UK' and c['columns']==['workspace_id','generation_id','sales_record_id'])]
        self.assertTrue(self.valid(d))
        d=copy.deepcopy(self.result)
        next(s for s in d['states'] if s['table']=='erp.tax_invoice')['values'].append('cancelled')
        self.assertTrue(self.valid(d))

    def test_exact_preview_mapping_and_accounts(self):
        d=copy.deepcopy(self.result)
        rule=next(c for c in d['constraints'] if c['table']=='erp.posting_rule' and c['kind']=='CHECK')
        rule['expression']=rule['expression'].replace("amount_basis = 'APPLY'","amount_basis = 'TOTAL'")
        self.assertTrue(self.valid(d))
        d=copy.deepcopy(self.result)
        next(c for c in d['code_lists'] if c['target']=='erp.account')['values'].append('ADVANCE')
        self.assertTrue(self.valid(d))

    def test_currency_and_restrict(self):
        d=copy.deepcopy(self.result)
        d['constraints']=[c for c in d['constraints'] if not(c['table']=='erp.receipt' and c['kind']=='CHECK' and c['expression']=="currency = 'KRW'")]
        self.assertTrue(self.valid(d))
        d=copy.deepcopy(self.result);d['relations'][-1]['on_delete']='CASCADE';self.assertTrue(self.valid(d))

    def test_dry_run_backup_and_byte_mtime_idempotence(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'schema.json';p.write_bytes(self.raw);before=p.stat().st_mtime_ns
            r=self.run_apply(p,'--check');self.assertEqual(r.returncode,0,r.stdout)
            self.assertEqual(p.read_bytes(),self.raw);self.assertEqual(p.stat().st_mtime_ns,before)
            self.assertFalse((p.parent/'backups').exists())
            r=self.run_apply(p);self.assertEqual(r.returncode,0,r.stdout)
            files=[p,*list((p.parent/'backups').iterdir())];self.assertEqual(len(files),2)
            self.assertEqual(files[1].read_bytes(),self.raw)
            snapshot={f:(f.read_bytes(),f.stat().st_mtime_ns) for f in files}
            r=self.run_apply(p);self.assertEqual(r.returncode,0,r.stdout)
            self.assertEqual(snapshot,{f:(f.read_bytes(),f.stat().st_mtime_ns) for f in files})
            self.assertEqual(len(list((p.parent/'backups').iterdir())),1)

    def test_invalid_input_and_applied_state_preserved(self):
        bad=copy.deepcopy(self.original);bad['relations'][0]['target']='core.missing'
        applied=copy.deepcopy(self.result);applied['relations'][-1]['on_delete']='CASCADE'
        for d in [dict(self.original,version='0.6.0'),dict(self.original,migration_revision='applied'),bad,applied]:
            with tempfile.TemporaryDirectory() as directory:
                p=Path(directory)/'schema.json';raw=json.dumps(d).encode();p.write_bytes(raw)
                self.assertNotEqual(self.run_apply(p).returncode,0)
                self.assertEqual(p.read_bytes(),raw);self.assertFalse((p.parent/'backups').exists())

    def test_atomic_replace_failure_preserves_source_and_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'schema.json';p.write_bytes(self.raw)
            with patch.object(sys,'argv',['apply_fs014b.py','--schema',str(p)]),patch('apply_fs014b.os.replace',side_effect=OSError('injected replace failure')):
                self.assertEqual(main(),1)
            self.assertEqual(p.read_bytes(),self.raw)
            self.assertEqual(next((p.parent/'backups').iterdir()).read_bytes(),self.raw)
            self.assertEqual(list(p.parent.glob('.fs014b-*')),[])


if __name__=='__main__':
    unittest.main()
