"""Complete theme transactions use disposable assets; never network or a device."""
import importlib.util
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
spec = importlib.util.spec_from_file_location('complete_theme', ROOT / 'tools/theme-pack.py')
theme = importlib.util.module_from_spec(spec)
spec.loader.exec_module(theme)


class CompleteThemeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.volume = self.root / 'volume'
        (self.volume / '.rockbox').mkdir(parents=True)
        (self.volume / '.rockbox/rockbox-info.txt').write_text(
            'Target: ipod6g\nVersion: 4.0-spectrum-1.0.0-e094c599fa\n')
        for name in ('config.cfg', 'rockbox.ipod', 'langs/AppleMenu40.lng', 'tagnavi_user.config'):
            path = self.volume / '.rockbox' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'preserved sentinel')

    def pack(self, ident='Example', setting='spectrum enabled: on'):
        pack = self.root / ident
        pack.mkdir()
        meta = {'schema': 3, 'id': ident, 'version': '1.0', 'target': 'ipod6g',
                'minimum_firmware_version': '1.0.0', 'required_skin_api': 2}
        (pack / 'pack.json').write_text(json.dumps(meta))
        files = {'.rockbox/wps/' + ident + '.sbs': b'%V(0,0,320,240,0)\n%Lt\n',
                 '.rockbox/themes/' + ident + '/licenses/NOTICE.txt': b'fixture'}
        for variant in ('Detail', 'Visualizer'):
            files['.rockbox/themes/' + ident + '-' + variant + '.cfg'] = (setting + '\nwps: /.rockbox/wps/' + ident + '-' + variant + '.wps\n'
                + 'sbs: /.rockbox/wps/' + ident + '.sbs\nfont: /.rockbox/fonts/' + ident + '-14.fnt\n').encode()
            files['.rockbox/wps/' + ident + '-' + variant + '.wps'] = (
                '%Fl(2,' + ident + '-14.fnt,10)\n%xl(bg,/.rockbox/wps/' + ident + '/background.bmp)\n').encode()
        for name, data in files.items():
            p = pack / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        assets = {'.rockbox/fonts/' + ident + '-14.fnt': b'RB12' + b'\0' * 32,
                  '.rockbox/wps/' + ident + '/background.bmp': b'BM' + b'\0' * 64}
        return pack, assets

    def build(self, pack, assets, suffix=''):
        dest = self.root / (pack.name + suffix + '.zip')
        with patch.object(theme, 'assemble', return_value=assets):
            theme.build(pack, dest)
        return dest

    def args(self, package, session):
        return SimpleNamespace(package=package, sha256=theme.digest(package.read_bytes()),
                               volume=self.volume, session=self.root / session, apply=True)

    def snapshot(self):
        return {str(p.relative_to(self.volume)): p.read_bytes() for p in self.volume.rglob('*') if p.is_file()}

    def test_complete_reproducible_and_exact_rollback(self):
        pack, assets = self.pack()
        a = self.build(pack, assets)
        self.assertEqual(a.read_bytes(), self.build(pack, assets, '-again').read_bytes())
        self.assertEqual(theme.verify(a)['metadata']['dependencies'], [])
        before = self.snapshot()
        args = self.args(a, 'session')
        args.apply = False
        theme.install(args)
        self.assertEqual(self.snapshot(), before)
        args.apply = True
        theme.install(args)
        theme.rollback(args)
        self.assertEqual(self.snapshot(), before)

    def test_independent_theme_namespaces_and_later_edit(self):
        a = self.args(self.build(*self.pack('First')), 'first-session')
        b = self.args(self.build(*self.pack('Second')), 'second-session')
        theme.install(a)
        before_second = self.snapshot()
        theme.install(b)
        theme.rollback(b)
        self.assertEqual(self.snapshot(), before_second)
        (self.volume / '.rockbox/fonts/First-14.fnt').write_bytes(b'later edit')
        with self.assertRaisesRegex(ValueError, 'changed'):
            theme.rollback(a)

    def test_missing_corrupt_asset_and_foreign_namespace(self):
        pack, assets = self.pack()
        with self.assertRaisesRegex(ValueError, 'missing assets'):
            self.build(pack, {})
        broken = dict(assets)
        broken['.rockbox/fonts/Example-14.fnt'] = b'not a font'
        with self.assertRaisesRegex(ValueError, 'font asset'):
            self.build(pack, broken)
        broken = dict(assets)
        broken['.rockbox/fonts/Other-14.fnt'] = b'RB12'
        with self.assertRaisesRegex(ValueError, 'namespace'):
            self.build(pack, broken)

    def test_audio_navigation_and_unsafe_paths_refused(self):
        for index, setting in enumerate(('volume: -1', 'eq enabled: off', 'lang: english',
                                         'root menu order: database', 'spectrum motion: punchy', 'visualization effect: auto')):
            pack, assets = self.pack('Unsafe' + str(index), setting)
            with self.assertRaisesRegex(ValueError, 'nonvisual'):
                self.build(pack, assets)
        for name in ('.rockbox/wps/Example/../../rockbox.ipod', '.rockbox/config.cfg',
                     '.rockbox/wps/Example/evil.rock', '.rockbox/fonts/Other-14.fnt'):
            with self.assertRaises(ValueError):
                theme.payload_path(name, {'schema': 3, 'id': 'Example'})

    def test_animation_requires_new_firmware_and_declared_capability(self):
        pack, assets = self.pack('Animated')
        meta_path = pack / 'pack.json'
        meta = json.loads(meta_path.read_text())
        skin = pack / '.rockbox/wps/Animated-Detail.wps'
        skin.write_text(skin.read_text() + '%pV(0,0,320,240,feedback,000000,00ff88,ff55bb)\n')
        with self.assertRaisesRegex(ValueError, 'skin API 3'):
            self.build(pack, assets)
        meta.update(required_skin_api=3)
        meta_path.write_text(json.dumps(meta))
        with self.assertRaisesRegex(ValueError, '1.1.0'):
            self.build(pack, assets)
        meta['minimum_firmware_version'] = '1.1.0'
        meta_path.write_text(json.dumps(meta))
        package = self.build(pack, assets)
        before = self.snapshot()
        with self.assertRaises(ValueError):
            theme.install(self.args(package, 'too-old'))
        self.assertEqual(before, self.snapshot())
        (self.volume / '.rockbox/rockbox-info.txt').write_text(
            'Target: ipod6g\nVersion: 4.0-spectrum-1.1.0-e094c599fa\n')
        theme.install(self.args(package, 'supported'))
        self.assertTrue((self.volume / '.rockbox/wps/Animated-Detail.wps').is_file())

    def test_archive_limits_and_corrupt_hash(self):
        package = self.build(*self.pack())
        oversized = self.root / 'oversized.zip'
        with ZipFile(package) as src, ZipFile(oversized, 'w') as dst:
            for name in src.namelist():
                dst.writestr(name, src.read(name))
            for i in range(257):
                dst.writestr('extra-' + str(i), b'')
        with self.assertRaisesRegex(ValueError, 'Oversized'):
            theme.verify(oversized)
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            theme.verify(package, 'incorrect')

    def test_relative_bitmap_and_optional_font_argument(self):
        files = {'.rockbox/wps/Example-Detail.wps': b'%Fl(2,Example-14.fnt,10)\n%xl(bg,relative.bmp)'}
        self.assertEqual(theme.dependencies(files), ['.rockbox/fonts/Example-14.fnt',
                         '.rockbox/wps/Example-Detail/relative.bmp'])

    def test_cfg_cannot_silently_select_external_skin(self):
        pack, assets = self.pack()
        cfg = pack / '.rockbox/themes/Example-Detail.cfg'
        cfg.write_text(cfg.read_text().replace('/.rockbox/wps/Example-Detail.wps', '../foreign.wps'))
        with self.assertRaisesRegex(ValueError, 'missing asset'):
            self.build(pack, assets)

    def test_asset_cache_and_member_fingerprints(self):
        from theme_assets import assemble, sha
        pack = self.root / 'locked'
        pack.mkdir()
        cache = self.root / 'cache'
        cache.mkdir()
        data = b'RB12-pinned-fixture'
        checksum = sha(data)
        cached = cache / checksum
        cached.write_bytes(data)
        source = {'url': 'https://example.invalid/font', 'sha256': checksum,
                  'format': 'raw', 'members': [{'target': '.rockbox/fonts/Example-14.fnt',
                  'sha256': checksum}]}
        (pack / 'assets.json').write_text(json.dumps({'sources': [source]}))
        with patch('theme_assets.subprocess.run') as network:
            self.assertEqual(assemble(pack, cache), {'.rockbox/fonts/Example-14.fnt': data})
            network.assert_not_called()
        cached.write_bytes(b'corrupt cache')
        with self.assertRaisesRegex(ValueError, 'Cached theme asset fingerprint'):
            assemble(pack, cache)
        cached.write_bytes(data)
        source['members'][0]['sha256'] = '0' * 64
        (pack / 'assets.json').write_text(json.dumps({'sources': [source]}))
        with self.assertRaisesRegex(ValueError, 'member fingerprint'):
            assemble(pack, cache)
        cached.unlink()
        target = self.root / 'symlink-target'
        target.write_bytes(data)
        cached.symlink_to(target)
        with self.assertRaisesRegex(ValueError, 'Unsafe theme asset cache'):
            assemble(pack, cache)

    def test_failed_copy_restores_existing_assets(self):
        args = self.args(self.build(*self.pack()), 'session')
        before = self.snapshot()
        original = theme.write_bytes
        calls = [0]
        def fail_once(path, data):
            calls[0] += 1
            if calls[0] == 4:
                raise OSError('injected copy failure')
            return original(path, data)
        with patch.object(theme, 'write_bytes', side_effect=fail_once):
            with self.assertRaises(OSError):
                theme.install(args)
        self.assertEqual(self.snapshot(), before)


if __name__ == '__main__':
    unittest.main()
