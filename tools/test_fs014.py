"""FS-014 regression tests. Only temporary files are mutated."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from apply_fs013 import transform, AFTER, counts, MASTERS, DROP
from audit_schema_isolation import audit
from validate_db_design import validate, design_names

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT/'docs/db/schema-metadata/backups/schema.before-FS-014.835668b772bc2b5a0aa09fcb4e479fc6e44900328716111d21865b0bf5d8bfb3.json'


class FS014Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = FIXTURE.read_bytes()
        cls.original = json.loads(cls.raw)
        cls.result = transform(cls.original)

    def test_inventory_and_mapping(self):
        self.assertEqual(counts(self.result), AFTER)
        names = {t['name'] for t in self.result['tables']}
        self.assertEqual(len(names), 61)
        self.assertFalse(names & (DROP | set(MASTERS)))
        self.assertTrue({n for targets in MASTERS.values() for n in targets} <= names)
        self.assertEqual({t['name'] for t in self.original['tables']}, {t['name'] for t in json.loads(self.raw)['tables']})
        self.assertEqual(validate(self.result, design_names()), [])

    def test_input_not_mutated(self):
        self.assertEqual(self.original, json.loads(self.raw))

    def test_r1_to_r5_reject_independent_violations(self):
        mutations = [
            ('R1', lambda d: d['relations'].append(dict(source='mes.item', target='erp.item'))),
            ('R2', lambda d: d['relations'].append(dict(source='mes.item', target='core.app_user'))),
            ('R3', lambda d: d['relations'].append(dict(source='core.workspace', target='fems.equipment'))),
            ('R4', lambda d: d['tables'].append(dict(name='learning.attempt', columns=[]))),
            ('R4', lambda d: d['tables'].append(dict(name='process_map.node', columns=[]))),
            ('R4', lambda d: d['tables'].append(dict(name='bems.energy_reading', columns=[]))),
            ('R5', lambda d: next(t for t in d['tables'] if t['name']=='mes.item')['columns'].pop(1)),
        ]
        for rule, mutation in mutations:
            with self.subTest(rule=rule):
                d = copy.deepcopy(self.result)
                mutation(d)
                self.assertTrue(any(e.startswith(rule+':') for e in audit(d)))

    def test_r5_nullable_scope_rejected(self):
        d = copy.deepcopy(self.result)
        next(c for t in d['tables'] if t['name']=='erp.item' for c in t['columns'] if c['name']=='generation_id')['nullable'] = True
        self.assertTrue(any(e.startswith('R5:') for e in audit(d)))

    def test_structural_corruption(self):
        for field, value in [('target', 'fems.absent'), ('target_columns', ['workspace_id','generation_id','absent']), ('on_delete', 'CASCADE')]:
            with self.subTest(field=field):
                d = copy.deepcopy(self.result)
                d['relations'][-1][field] = value
                self.assertTrue(validate(d, design_names()))

    def test_scope_type_unique_and_calendar(self):
        mutations = [
            lambda d: d['relations'][-1].update(columns=['equipment_id'], target_columns=['id']),
            lambda d: next(c for t in d['tables'] if t['name']=='fems.production_record' for c in t['columns'] if c['name']=='equipment_id').update(type='varchar(40)'),
            lambda d: d['constraints'].__setitem__(slice(None), [c for c in d['constraints'] if not (c['table']=='fems.equipment' and c['kind']=='UK' and c['columns']==['workspace_id','generation_id','id'])]),
            lambda d: d['constraints'].__setitem__(slice(None), [c for c in d['constraints'] if not (c['table']=='mes.production_plan_line' and c['kind']=='CHECK' and 'target_week' in c['expression'])]),
        ]
        for mutation in mutations:
            d = copy.deepcopy(self.result)
            mutation(d)
            self.assertTrue(validate(d, design_names()))

    def run_apply(self, path, *extra):
        return subprocess.run([sys.executable, str(ROOT/'tools/apply_fs013.py'), '--schema', str(path), *extra], capture_output=True, text=True)

    def test_backup_dry_run_and_byte_idempotence(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)/'schema.json'
            p.write_bytes(self.raw)
            before = p.stat().st_mtime_ns
            dry = self.run_apply(p, '--check')
            self.assertEqual(dry.returncode, 0, dry.stdout)
            self.assertEqual(p.read_bytes(), self.raw)
            self.assertEqual(p.stat().st_mtime_ns, before)
            self.assertFalse((p.parent/'backups').exists())
            applied = self.run_apply(p)
            self.assertEqual(applied.returncode, 0, applied.stdout)
            backups = list((p.parent/'backups').iterdir())
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), self.raw)
            snapshot = {f: (f.read_bytes(), f.stat().st_mtime_ns) for f in [p, *backups]}
            again = self.run_apply(p)
            self.assertEqual(again.returncode, 0, again.stdout)
            self.assertEqual(snapshot, {f: (f.read_bytes(), f.stat().st_mtime_ns) for f in [p, *backups]})
            self.assertEqual(list((p.parent/'backups').iterdir()), backups)

    def test_invalid_input_leaves_source_untouched(self):
        variants = [dict(self.original, version='0.5.0'), dict(self.original, migration_revision='applied')]
        damaged = copy.deepcopy(self.original)
        damaged['relations'][0]['target'] = 'core.missing'
        variants.append(damaged)
        for d in variants:
            with tempfile.TemporaryDirectory() as directory:
                p = Path(directory)/'schema.json'
                raw = json.dumps(d).encode()
                p.write_bytes(raw)
                result = self.run_apply(p)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(p.read_bytes(), raw)
                self.assertFalse((p.parent/'backups').exists())

    def test_invalid_applied_state_is_not_silently_accepted(self):
        d = copy.deepcopy(self.result)
        d['relations'][-1]['on_delete'] = 'CASCADE'
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)/'schema.json'
            raw = json.dumps(d).encode()
            p.write_bytes(raw)
            self.assertNotEqual(self.run_apply(p).returncode, 0)
            self.assertEqual(p.read_bytes(), raw)

    def test_cli_audit_exit_status(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)/'schema.json'
            for d, code in [(self.result, 0), (self.original, 1)]:
                p.write_text(json.dumps(d))
                result = subprocess.run([sys.executable, str(ROOT/'tools/audit_schema_isolation.py'), '--schema', str(p)], capture_output=True)
                self.assertEqual(result.returncode, code)


if __name__ == '__main__':
    unittest.main()
