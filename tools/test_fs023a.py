"""FS-023a: R6(다른 솔루션은 interface만 import)과 schema.json 반영의 멱등성."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

import apply_fs023a
from audit_schema_isolation import audit, audit_imports

ROOT = Path(__file__).resolve().parents[1]


class R6Test(unittest.TestCase):
    def check(self, owner, code):
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp)/owner
            package.mkdir()
            (package/'service.py').write_text(code, encoding='utf-8')
            return audit_imports(Path(tmp))

    def test_interface_import_is_allowed(self):
        self.assertEqual(self.check('qms', 'from fs.mes import interface\nfrom fs.mes.interface import lot_snapshot\nimport fs.mes.interface\n'), [])

    def test_other_module_import_is_rejected(self):
        errors = self.check('qms', 'from fs.mes import repository\nfrom fs.mes.service import x\nimport fs.erp.sales\n')
        self.assertEqual(len(errors), 3)
        self.assertTrue(all(e.startswith('R6:') for e in errors))

    def test_common_and_own_package_are_allowed(self):
        self.assertEqual(self.check('mes', 'from fs.common.scope import read_scope\nfrom fs.mes import repository\n'), [])

    def test_current_backend_passes(self):
        self.assertEqual(audit_imports(), [])


class ApplyTest(unittest.TestCase):
    def test_apply_is_idempotent_and_isolated(self):
        current = json.loads((ROOT/'docs/db/schema-metadata/schema.json').read_text(encoding='utf-8'))
        again = copy.deepcopy(current)
        self.assertFalse(apply_fs023a.apply(again))
        self.assertEqual(again, current)
        self.assertEqual(sum(t['name'].startswith('qms.') for t in current['tables']), 15)
        self.assertEqual(audit(current), [])


if __name__ == '__main__':
    unittest.main()
