import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile

from tools.build_candidate import build_bundle, verify_bundle
from tests import test_runtime_wheel as wheel_fixtures


class CandidateBundleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        source = Path(__file__).resolve().parents[1]
        for folder in ('custom_components', 'docs', 'examples', 'packaging', 'tools'):
            shutil.copytree(source / folder, self.root / folder,
                            ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copyfile(source / 'README.md', self.root / 'README.md')
        self.wheels = self.root / 'wheels'
        self.wheels.mkdir()
        wheel, digest = wheel_fixtures.WheelTests().wheel(self.wheels)
        tag = 'cp314-cp314-musllinux_1_2_aarch64'
        (self.root / 'packaging/runtime-wheels.json').write_text(json.dumps({
            'wheels': [{'filename': wheel.name, 'sha256': digest, 'tag': tag}]}))
        self.cache = self.root / 'cache'
        self.cache.mkdir()
        pip = b'isolated fixture pip payload'
        (self.cache / 'pip-fixture.whl').write_bytes(pip)
        (self.root / 'packaging/inputs.lock.json').write_text(json.dumps({'wheels': [{
            'filename': 'pip-fixture.whl', 'sha256': hashlib.sha256(pip).hexdigest()}]}))

    def build(self, name):
        output = self.root / name
        result = build_bundle(self.root, self.wheels, self.cache, output)
        return output, result

    def test_repeat_packaging_is_identical_and_private_inputs_are_excluded(self):
        (self.root / '.private').mkdir()
        (self.root / '.private/inventory.json').write_text('secret-home-partition')
        (self.root / 'custom_components/homycloud_local/inventory.json').write_text('secret-home-partition')
        first, report = self.build('first.zip')
        second, repeated = self.build('second.zip')
        self.assertEqual(report['sha256'], repeated['sha256'])
        self.assertEqual(first.read_bytes(), second.read_bytes())
        with zipfile.ZipFile(first) as archive:
            self.assertIn('tools/__init__.py', archive.namelist())
            self.assertEqual(
                archive.read('custom_components/homycloud_local/brand/icon.png'),
                (self.root / 'custom_components/homycloud_local/brand/icon.png').read_bytes(),
            )
            self.assertFalse(any('.private' in name or name.endswith('/inventory.json')
                                 for name in archive.namelist()))
            self.assertTrue(all(b'secret-home-partition' not in archive.read(name)
                                for name in archive.namelist()))
        with self.assertRaises(FileExistsError):
            self.build('first.zip')
        self.assertEqual(verify_bundle(first)['sha256'], report['sha256'])

    def test_modified_payload_is_rejected(self):
        original, _ = self.build('original.zip')
        modified = self.root / 'modified.zip'
        with zipfile.ZipFile(original) as source, zipfile.ZipFile(modified, 'w') as output:
            for name in source.namelist():
                data = b'altered' if name == 'README.md' else source.read(name)
                output.writestr(name, data)
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            verify_bundle(modified)

    def test_added_payload_and_unsafe_paths_are_rejected(self):
        for entry in ('unlisted.txt', '../escape'):
            with self.subTest(entry=entry):
                original, _ = self.build('extra-' + str(len(entry)) + '.zip')
                with zipfile.ZipFile(original, 'a') as archive:
                    archive.writestr(entry, b'unexpected')
                with self.assertRaises(ValueError):
                    verify_bundle(original)

    def test_corrupt_pip_is_rejected_before_creating_output(self):
        (self.cache / 'pip-fixture.whl').write_bytes(b'wrong')
        with self.assertRaisesRegex(ValueError, 'pip checksum mismatch'):
            self.build('bad.zip')
        self.assertFalse((self.root / 'bad.zip').exists())
