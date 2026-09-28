import copy
import json
import unittest
from pathlib import Path
import apply_fs026a
from validate_fs026a import validate_extension

class ExtensionTest(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((Path(__file__).resolve().parents[1]/'docs/db/schema-metadata/schema.json').read_text())

    def test_metadata_application_is_idempotent(self):
        again=copy.deepcopy(self.data)
        self.assertFalse(apply_fs026a.apply(again))
        self.assertEqual(again,self.data)
        self.assertEqual(validate_extension(again),[])

    def test_missing_claim_guard_is_rejected(self):
        self.data['constraints']=[c for c in self.data['constraints'] if not(c['table']=='wms.source_claim' and c['kind']=='UK_PARTIAL')]
        self.assertTrue(validate_extension(self.data))

    def test_missing_null_lot_guard_is_rejected(self):
        self.data['constraints']=[c for c in self.data['constraints'] if not(c['table']=='wms.stock_reservation_line' and c['kind']=='UK_PARTIAL' and c['expression'].endswith('WHERE lot_no IS NULL'))]
        self.assertTrue(validate_extension(self.data))
