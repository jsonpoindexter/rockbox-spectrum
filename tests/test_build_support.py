#!/usr/bin/env python3
"""Verify input/cache failure cases without networks or a device. GPL-2.0-or-later."""
import hashlib
import importlib.util
import io
import json
import tarfile
import tempfile
import unittest
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import firmware_version as version
spec = importlib.util.spec_from_file_location('bootstrap', ROOT / 'tools/bootstrap-toolchain.py')
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


class InputTests(unittest.TestCase):
    def test_corrupt_existing_download_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'source.tar.gz'
            target.write_bytes(b'wrong')
            with patch.object(bootstrap.urllib.request, 'urlopen') as download:
                with self.assertRaisesRegex(ValueError, 'fingerprint mismatch'):
                    bootstrap.fetch('https://example.invalid', target, '0' * 64)
                download.assert_not_called()

    def test_bad_download_does_not_commit_partial_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'source.tar.gz'
            with patch.object(bootstrap.urllib.request, 'urlopen', return_value=io.BytesIO(b'wrong')):
                with self.assertRaisesRegex(ValueError, 'fingerprint mismatch'):
                    bootstrap.fetch('https://example.invalid', target, '0' * 64)
            self.assertFalse(target.exists())
            self.assertFalse(target.with_name(target.name + '.partial').exists())

    def test_exact_download_and_cache_damage(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            payload = b'correct'
            digest = hashlib.sha256(payload).hexdigest()
            target = root / 'input'
            with patch.object(bootstrap.urllib.request, 'urlopen', return_value=io.BytesIO(payload)):
                bootstrap.fetch('https://example.invalid', target, digest)
            record = {'input_fingerprint': 'key', 'prefix': str(root), 'files': bootstrap.tree_manifest(root)}
            (root / 'toolchain-manifest.json').write_text(json.dumps(record))
            self.assertTrue(bootstrap.verify_cache(root, 'key'))
            with self.assertRaisesRegex(ValueError, 'pinned inputs'):
                bootstrap.verify_cache(root, 'different-key')
            target.write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError, 'file verification'):
                bootstrap.verify_cache(root, 'key')

    def test_archive_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / 'bad.tar'
            with tarfile.open(archive, 'w') as out:
                entry = tarfile.TarInfo('rockbox-revision/../escaped')
                entry.size = 1
                out.addfile(entry, io.BytesIO(b'x'))
            with self.assertRaisesRegex(ValueError, 'Unsafe'):
                bootstrap.extract_source(archive, root / 'source', 'revision')
            self.assertFalse((root / 'escaped').exists())


class VersionTests(unittest.TestCase):
    def test_initial_release_and_legacy_apis(self):
        self.assertEqual(version.current_version(), '4.0-spectrum-1.0.0-e094c599fa')
        for label, api, skin in [('1.0.0', 275, 2), ('1.1.0', 275, 2),
                                 ('v1', 274, 1), ('v1-fast3', 274, 1),
                                 ('v1-fast4', 275, 1), ('v1-fast9', 275, 1), ('v1-fast10', 275, 2)]:
            info = 'Target: ipod6g\nVersion: 4.0-spectrum-' + label + '-e094c599fa\n'
            parsed = version.firmware(info)
            self.assertEqual((parsed.plugin_api, parsed.skin_api), (api, skin))
            self.assertEqual(version.firmware(info.replace('\n', '\r\n')), parsed)

    def test_invalid_and_ambiguous_versions_refused(self):
        for value in ['4.0', '4.0-spectrum-v1-test', '4.0-spectrum-01.0.0-e094c599fa',
                      '4.0-spectrum-2.0.0-e094c599fa', '4.0-spectrum-1.0-e094c599fa',
                      '4.0-spectrum-1.0.0-invalid', '4.0-spectrum-v1-fast0-e094c599fa']:
            with self.assertRaises(ValueError):
                version.firmware('Target: ipod6g\nVersion: ' + value + '\n')
        current = 'Target: ipod6g\nVersion: ' + version.current_version() + '\n'
        for info in [current.replace('ipod6g', 'ipodvideo'), current + 'Version: 4.0\n', current + 'Target: ipod6g\n']:
            with self.assertRaises(ValueError): version.firmware(info)

    def test_theme_requirements_use_versions_and_capabilities(self):
        styled = {'schema': 2, 'minimum_firmware_version': '1.0.0', 'required_skin_api': 2}
        presets = dict(styled, required_skin_api=1)
        for label, styles, controls in [('1.0.0', True, True), ('v1-fast10', True, True),
                                      ('v1-fast9', False, True), ('v1-fast4', False, True),
                                      ('v1-fast3', False, False)]:
            info = 'Target: ipod6g\nVersion: 4.0-spectrum-' + label + '-e094c599fa\n'
            self.assertEqual(version.theme_compatible(info, styled), styles)
            self.assertEqual(version.theme_compatible(info, presets), controls)
        info = 'Target: ipod6g\nVersion: ' + version.current_version() + '\n'
        self.assertFalse(version.theme_compatible(info, dict(styled, minimum_firmware_version='1.1.0')))
        self.assertTrue(version.theme_compatible(info, {'schema': 1, 'minimum_firmware_fast': 10}))

    def test_invalid_semantic_versions(self):
        for text in [None, '1', '1.0', '01.0.0', '1.0.0-beta', '-1.0.0']:
            with self.assertRaises(ValueError): version.semver(text)


if __name__ == '__main__':
    unittest.main()
