"""Reproducible theme packs and disposable theme-only transactions. No device."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from types import SimpleNamespace
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('theme', ROOT / 'tools/theme-pack.py')
theme = importlib.util.module_from_spec(spec)
spec.loader.exec_module(theme)


class ThemeTrial(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.package = self.root / 'theme.zip'
        self.meta = theme.build(ROOT / 'theme-packs/ClassicSpectrum', self.package)['metadata']
        self.volume = self.root / 'volume'; self.volume.mkdir()
        for name in self.meta['dependencies']:
            path = self.volume / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(b'asset')
        self.active = self.volume / '.rockbox'
        (self.active / 'rockbox-info.txt').write_text('Target: ipod6g\nVersion: 4.0-spectrum-1.0.0-e094c599fa\n')
        (self.active / 'rockbox.ipod').write_bytes(b'firmware sentinel')
        (self.active / 'config.cfg').write_bytes(b'personal settings sentinel')
        (self.active / 'wps/ClassicSpectrum.wps').write_bytes(b'previous theme')
        (self.volume / 'music.mp3').write_bytes(b'music sentinel')
        self.args = SimpleNamespace(package=self.package, sha256=theme.digest(self.package.read_bytes()),
                                    volume=self.volume, session=self.root / 'session', apply=False)

    def snapshot(self):
        return {p.relative_to(self.volume).as_posix():p.read_bytes() for p in self.volume.rglob('*') if p.is_file()}

    def test_reproducible_all_packs(self):
        for pack in sorted((ROOT / 'theme-packs').iterdir()):
            first, second = self.root / (pack.name + '.zip'), self.root / (pack.name + '-again.zip')
            theme.build(pack, first); theme.build(pack, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            theme.verify(first)

    def test_theme_only_and_exact_rollback(self):
        before = self.snapshot()
        theme.install(self.args); self.assertEqual(self.snapshot(), before); self.assertFalse(self.args.session.exists())
        self.args.apply = True; theme.install(self.args)
        after = self.snapshot()
        payloads = set(self.meta['files'])
        self.assertEqual({n for n in set(before)|set(after) if before.get(n)!=after.get(n)}, payloads)
        self.args.apply = False; theme.rollback(self.args); self.assertEqual(self.snapshot(), after)
        self.args.apply = True; theme.rollback(self.args); self.assertEqual(self.snapshot(), before)

    def test_old_firmware_and_missing_asset_refused(self):
        info = self.active / 'rockbox-info.txt'; current = info.read_bytes()
        info.write_bytes(b'Target: ipod6g\nVersion: 4.0-spectrum-v1-fast9-e094c599fa\n')
        with self.assertRaisesRegex(ValueError, '1.0.0'): theme.install(self.args)
        info.write_bytes(current)
        (self.volume / self.meta['dependencies'][0]).unlink()
        with self.assertRaisesRegex(ValueError, 'original assets'): theme.install(self.args)
        self.assertFalse(self.args.session.exists())

    def test_legacy_styled_firmware_still_accepted(self):
        (self.active / 'rockbox-info.txt').write_text('Target: ipod6g\nVersion: 4.0-spectrum-v1-fast10-e094c599fa\n')
        self.args.apply = True
        theme.install(self.args)
        theme.rollback(self.args)

    def test_legacy_schema1_package_still_accepted(self):
        legacy = self.root / 'legacy.zip'
        with ZipFile(self.package) as src, ZipFile(legacy, 'w') as dst:
            for name in src.namelist():
                data = src.read(name)
                if name == 'theme-pack.json':
                    meta = json.loads(data)
                    meta['schema'] = 1; meta['minimum_firmware_fast'] = 10
                    meta.pop('minimum_firmware_version'); meta.pop('required_skin_api')
                    data = json.dumps(meta).encode()
                dst.writestr(name, data)
        self.args.package = legacy; self.args.sha256 = theme.digest(legacy.read_bytes())
        self.args.apply = True
        theme.install(self.args); theme.rollback(self.args)

    def test_later_theme_edit_refuses_rollback(self):
        self.args.apply = True; theme.install(self.args)
        (self.active / 'wps/ClassicSpectrum.wps').write_bytes(b'newer edit')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'changed'): theme.rollback(self.args)
        self.assertEqual(self.snapshot(), before)

    def test_payload_and_symlink_rejections(self):
        with self.assertRaises(ValueError): theme.payload_path('.rockbox/rockbox.ipod')
        with self.assertRaises(ValueError): theme.payload_path('.rockbox/config.cfg')
        with self.assertRaises(ValueError): theme.payload_path('.rockbox/wps/../themes/test.cfg')
        with self.assertRaises(ValueError): theme.verify(self.package, 'wrong hash')
        bad = self.root / 'bad.zip'
        with ZipFile(self.package) as src, ZipFile(bad, 'w') as dst:
            for name in src.namelist():
                dst.writestr(name, src.read(name))
            dst.writestr('.rockbox/rockbox.ipod', b'forbidden')
        with self.assertRaisesRegex(ValueError, 'member mismatch'): theme.verify(bad)
        (self.active / 'wps/ClassicSpectrum.wps').unlink()
        (self.active / 'wps/ClassicSpectrum.wps').symlink_to(self.root / 'elsewhere')
        with self.assertRaisesRegex(ValueError, 'symlink'): theme.install(self.args)

    def test_corrupt_payload_and_case_alias_refused(self):
        for suffix, mutate in [('payload', True), ('case', False)]:
            bad = self.root / (suffix + '.zip')
            with ZipFile(self.package) as src, ZipFile(bad, 'w') as dst:
                for name in src.namelist():
                    data = src.read(name)
                    if mutate and name.endswith('ClassicSpectrum.wps'): data += b'changed'
                    dst.writestr(name, data)
                if not mutate:
                    dst.writestr('.rockbox/wps/classicspectrum.wps', b'case alias')
            with self.assertRaisesRegex(ValueError, 'hash mismatch' if mutate else 'Duplicate'):
                theme.verify(bad)

    def test_rollback_fault_keeps_installed_theme(self):
        self.args.apply = True; theme.install(self.args)
        installed = self.snapshot(); write = theme.write_bytes; calls = 0
        def fail_once(path, data):
            nonlocal calls
            calls += 1
            if calls == 1: raise OSError('injected rollback fault')
            write(path, data)
        with patch.object(theme, 'write_bytes', side_effect=fail_once):
            with self.assertRaisesRegex(OSError, 'injected'): theme.rollback(self.args)
        self.assertEqual(self.snapshot(), installed)
        theme.rollback(self.args)
        self.assertEqual((self.active / 'wps/ClassicSpectrum.wps').read_bytes(), b'previous theme')

    def test_write_failure_restores_previous_files(self):
        before = self.snapshot(); self.args.apply = True
        write = theme.write_bytes; calls = 0
        def fail_once(path, data):
            nonlocal calls
            calls += 1
            if calls == 2: raise OSError('injected write fault')
            write(path, data)
        with patch.object(theme, 'write_bytes', side_effect=fail_once):
            with self.assertRaisesRegex(OSError, 'injected'): theme.install(self.args)
        self.assertEqual(self.snapshot(), before)
        self.assertIn('restored', json.loads((self.args.session / 'theme-trial.json').read_text())['activation'])


if __name__ == '__main__': unittest.main()
