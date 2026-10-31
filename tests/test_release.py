import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile

from tools.build_release import build_release, release_version


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        source = Path(__file__).resolve().parents[1] / 'custom_components'
        shutil.copytree(source, self.root / 'custom_components',
                        ignore=shutil.ignore_patterns('__pycache__'))

    def test_tags_and_prereleases(self):
        for tag, expected, prerelease in (
            ('v1.2.3', '1.2.3', False),
            ('v0.2.1-dev', '0.2.1.dev0', True),
            ('v1.2.3-rc.1', '1.2.3rc1', True),
            ('v1.2.3-beta.2', '1.2.3b2', True),
        ):
            with self.subTest(tag=tag):
                self.assertEqual(release_version(tag, '0.0.1'), (expected, prerelease))
        self.assertEqual(release_version(None, '0.2.1-dev'), ('0.2.1.dev0', True))
        for tag in ('main', 'vlatest', 'v1.2', 'v01.2.3', 'v1.2.3\nX=bad', 'v1.2.3;pwd'):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                release_version(tag, '0.0.1')

    def test_zip_layout_version_and_private_file_exclusion(self):
        component = self.root / 'custom_components/homycloud_local'
        original = (component / 'manifest.json').read_bytes()
        (component / 'inventory.json').write_text('PRIVATE_SENTINEL')
        (component / 'protocol/private.json').write_text('PRIVATE_SENTINEL')
        (component / '.private').mkdir()
        (component / '.private/password.txt').write_text('PRIVATE_SENTINEL')
        output = self.root / 'release'
        result = build_release(self.root, output, tag='v1.2.3', commit='a' * 40)
        self.assertFalse(result['native_runtime_bundled'])
        with zipfile.ZipFile(output / 'homycloud_local.zip') as archive:
            names = archive.namelist()
            self.assertIn('__init__.py', names)
            self.assertIn('protocol/schemas.json', names)
            self.assertEqual(json.loads(archive.read('manifest.json'))['version'], '1.2.3')
            self.assertFalse(any('private' in name or name.endswith('.whl') for name in names))
            self.assertTrue(all(b'PRIVATE_SENTINEL' not in archive.read(name) for name in names))
            self.assertEqual(archive.read('brand/icon.png'), (component / 'brand/icon.png').read_bytes())
        self.assertEqual((component / 'manifest.json').read_bytes(), original)
        for line in (output / 'SHA256SUMS').read_text().splitlines():
            expected, name = line.split('  ')
            self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), expected)

    def test_identical_inputs_give_identical_archives_and_metadata(self):
        first, second = self.root / 'first', self.root / 'second'
        build_release(self.root, first, tag='v1.2.3-rc.1', commit='a' * 40)
        build_release(self.root, second, tag='v1.2.3-rc.1', commit='a' * 40)
        for name in ('homycloud_local.zip', 'release-manifest.json', 'SHA256SUMS'):
            self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())
        with self.assertRaises(FileExistsError):
            build_release(self.root, first, tag='v1.2.3')

    def test_invalid_inputs_do_not_create_release_directory(self):
        output = self.root / 'invalid'
        with self.assertRaises(ValueError):
            build_release(self.root, output, tag='v1.2.3', commit='not-a-commit')
        self.assertFalse(output.exists())
        (self.root / 'custom_components/homycloud_local/brand/icon.png').unlink()
        with self.assertRaises(ValueError):
            build_release(self.root, output, tag='v1.2.3')
        self.assertFalse(output.exists())
