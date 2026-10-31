import json
import tempfile
import unittest
from pathlib import Path
from custom_components.homycloud_local.runtime import load_runtime


class RuntimeTests(unittest.TestCase):
    def test_mqtt_secrets_are_discarded(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'private.json'
            path.write_text(json.dumps({'devices':[{'id':'fake'}],'partition':'fake','dds_xml':'<CycloneDDS/>','mqtt_password':'test-only-not-real','mqtt_username':'fake'}),encoding='utf-8')
            loaded=load_runtime(path)
            self.assertEqual(set(loaded),{'devices','partition','dds_xml'})

    def test_empty_inventory_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'private.json'
            path.write_text(json.dumps({'devices':[],'partition':'fake','dds_xml':'x'}),encoding='utf-8')
            with self.assertRaises(ValueError):load_runtime(path)
