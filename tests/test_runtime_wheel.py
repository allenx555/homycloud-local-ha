import hashlib
import tempfile
from pathlib import Path
import unittest
import zipfile
from tools.runtime_install_plan import inspect_wheel


class WheelTests(unittest.TestCase):
    def wheel(self,root,tag='cp314-cp314-musllinux_1_2_aarch64',extra=None):
        path=root/'test.whl'
        with zipfile.ZipFile(path,'w') as archive:
            archive.writestr('cyclonedds-11.0.1.dist-info/METADATA','Name: cyclonedds\nVersion: 11.0.1+homycloud.2\n')
            archive.writestr('cyclonedds-11.0.1.dist-info/WHEEL','Wheel-Version: 1.0\nTag: '+tag+'\n')
            archive.writestr('cyclonedds.libs/libddsc-fake.so.11',b'fake test data')
            archive.writestr('cyclonedds/THIRD_PARTY_LICENSES/LICENSE',b'fixture license')
            if extra:archive.writestr(extra,b'bad')
        return path,hashlib.sha256(path.read_bytes()).hexdigest()

    def test_accepts_expected_metadata_and_compatible_tag(self):
        with tempfile.TemporaryDirectory() as folder:
            path,digest=self.wheel(Path(folder))
            result=inspect_wheel(path,digest,{'cp314-cp314-musllinux_1_2_aarch64'})
            self.assertEqual(result['version'],'11.0.1+homycloud.2')

    def test_rejects_hash_and_platform_mismatch(self):
        with tempfile.TemporaryDirectory() as folder:
            path,digest=self.wheel(Path(folder))
            with self.assertRaises(ValueError):inspect_wheel(path,'0'*64,{'cp314-cp314-musllinux_1_2_aarch64'})
            with self.assertRaises(ValueError):inspect_wheel(path,digest,{'cp313-cp313-win_amd64'})

    def test_rejects_traversal_even_with_correct_checksum(self):
        with tempfile.TemporaryDirectory() as folder:
            path,digest=self.wheel(Path(folder),extra='../escape')
            with self.assertRaises(ValueError):inspect_wheel(path,digest,{'cp314-cp314-musllinux_1_2_aarch64'})
