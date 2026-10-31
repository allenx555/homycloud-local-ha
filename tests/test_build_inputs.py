import hashlib
import io
import tempfile
from pathlib import Path
import unittest
from tools.prepare_build_inputs import cached_input, deterministic_tar


class BuildInputTests(unittest.TestCase):
    def test_tar_is_identical_despite_input_metadata_and_order(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);a=root/'a';b=root/'b';a.write_bytes(b'one');b.write_bytes(b'two')
            first=root/'first.tar';second=root/'second.tar'
            deterministic_tar(first,[('b',b),('a',a)])
            a.chmod(0o600)
            deterministic_tar(second,[('a',a),('b',b)])
            self.assertEqual(first.read_bytes(),second.read_bytes())

    def test_offline_cache_is_verified_and_not_replaced(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);target=root/'file';target.write_bytes(b'bad')
            item={'filename':'file','sha256':hashlib.sha256(b'good').hexdigest(),'url':'https://example.invalid/file'}
            with self.assertRaises(ValueError):cached_input(item,root,offline=True)
            self.assertEqual(target.read_bytes(),b'bad')

    def test_bad_download_never_becomes_cached_input(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            item={'filename':'file','sha256':hashlib.sha256(b'good').hexdigest(),'url':'https://example.invalid/file'}
            with self.assertRaises(ValueError):cached_input(item,root,opener=lambda *a,**k:io.BytesIO(b'bad'))
            self.assertEqual(list(root.iterdir()),[])

    def test_unsafe_filename_and_missing_offline_inputs_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in ['../escape','..\\escape']:
                item={'filename':name,'sha256':'x','url':'https://example.invalid/file'}
                with self.subTest(name=name),self.assertRaises(ValueError):cached_input(item,root,offline=True)
            with self.assertRaises(FileNotFoundError):cached_input({'filename':'missing','sha256':'x'},root,offline=True)
