"""Synthetic files and mocked debugfs, NOT parsing a real Android filesystem."""
import gzip
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import shutil
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'inspect-ready-gsi.py'
spec = importlib.util.spec_from_file_location('inspect_gsi', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class InspectGSITests(unittest.TestCase):
    def test_property_and_elf_parsing(self):
        props = module.parse_props(b'# comment\nro.build.version.sdk=34\nsecret.key=ignored\nro.config.low_ram=true\n')
        self.assertEqual(props, {'ro.build.version.sdk': '34', 'ro.config.low_ram': 'true'})
        with self.assertRaises(ValueError):
            module.parse_props(b'ro.build.version.sdk=34\nro.build.version.sdk=33')
        data = bytearray(20)
        data[:6] = b'\x7fELF\x01\x01'
        data[18:20] = (40).to_bytes(2, 'little')
        self.assertEqual(module.elf_header(data), {'class_bits': 32, 'machine': 40})
        self.assertIsNone(module.elf_header(b'not elf'))

    def test_listing_parsing_and_guards(self):
        data = b'/2/040755/0/0/.//\n/3/040755/0/0/..//\n/42/040755/0/0/Settings//\n/43/100644/0/0/example.rc/123/\n'
        entries = module.parse_listing(data)
        self.assertEqual([e['name'] for e in entries], ['Settings', 'example.rc'])
        self.assertEqual(entries[0]['kind'], 'directory')
        self.assertEqual(entries[1]['kind'], 'file')
        for value in (b'not a listing', b'/x/040755/0/0/Foo//', b'/4/invalid/0/0/Foo//',
                      b'/4/040755/0/0/bad\x01name//', b'/4/040755/0/0/Foo//\n' * 513):
            with self.assertRaises(ValueError):
                module.parse_listing(value)

    def test_inspection_and_failures(self):
        for case in ('success', 'bad_hash', 'missing_props', 'debugfs_timeout', 'expanded_limit', 'bad_header'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                raw = bytearray(4096)
                if case != 'bad_header':
                    raw[1080:1082] = b'\x53\xef'
                image = root / 'candidate.gz'
                image.write_bytes(gzip.compress(raw))
                expected = hashlib.sha256(image.read_bytes()).hexdigest()
                if case == 'bad_hash': expected = '0' * 64
                def reader(raw_path, command, work):
                    self.assertTrue(raw_path.is_file())
                    if case == 'debugfs_timeout': raise subprocess.TimeoutExpired('debugfs', 25)
                    if 'build.prop' in command and case != 'missing_props':
                        return b'ro.build.version.sdk=34\nro.build.version.security_patch=2026-11-01\n', ''
                    if command == 'ls -p /system/app':
                        return b'/42/040755/0/0/Settings//\n', ''
                    return b'', 'unavailable'
                with patch.object(module, 'read_debugfs', side_effect=reader) as debugfs:
                    result = module.inspect(image, expected, root / 'report',
                                            maximum=1 if case == 'expanded_limit' else 8192)
                self.assertEqual(result['passed'], case == 'success')
                if case == 'success':
                    self.assertEqual(result['inventory_by_path']['/system/app']['entries'][0]['name'], 'Settings')
                    self.assertEqual(result['inventory_by_path']['/product/app']['status'], 'unavailable')
                self.assertFalse(result['publisher_authenticated'])
                self.assertFalse(result['boot_tested'])
                self.assertIsNone(result['device_compatible'])
                self.assertFalse(list(root.glob('.gsi-inspection-*')))
                if case in ('bad_hash', 'expanded_limit', 'bad_header'):
                    debugfs.assert_not_called()
                with self.assertRaises(ValueError):
                    module.inspect(image, expected, root / 'report')

    @unittest.skipUnless(shutil.which('debugfs') and shutil.which('mkfs.ext4'),
                         'host e2fsprogs unavailable; real ext4 fixture NOT tested here')
    def test_real_ext4_fixture_without_mount(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tree = root / 'tree'
            (tree / 'system/bin').mkdir(parents=True)
            (tree / 'system/app/FixtureApp').mkdir(parents=True)
            (tree / 'system/build.prop').write_text('ro.build.version.sdk=34\nro.build.version.security_patch=2026-11-01\n')
            elf = bytearray(20)
            elf[:6] = b'\x7fELF\x01\x01'
            elf[18:20] = (40).to_bytes(2, 'little')
            (tree / 'system/bin/app_process32').write_bytes(elf)
            raw = root / 'fixture.raw'
            with raw.open('wb') as stream:
                stream.truncate(16 * 1024**2)
            subprocess.run(['mkfs.ext4', '-q', '-F', '-d', str(tree), str(raw)], check=True,
                           capture_output=True, timeout=20)
            image = root / 'fixture.gz'
            with raw.open('rb') as source, gzip.open(image, 'wb') as dest:
                shutil.copyfileobj(source, dest)
            expected = hashlib.sha256(image.read_bytes()).hexdigest()
            result = module.inspect(image, expected, root / 'report', maximum=32 * 1024**2)
            self.assertTrue(result['passed'], result)
            self.assertEqual(result['properties_by_path']['/system/build.prop']['ro.build.version.sdk'], '34')
            self.assertEqual(result['elf_by_path']['/system/bin/app_process32']['class_bits'], 32)
            self.assertFalse(result['boot_tested'])
            self.assertIn('FixtureApp', [e['name'] for e in result['inventory_by_path']['/system/app']['entries']])

    def test_debugfs_readonly_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def run(args, **kwargs):
                self.assertEqual(args, ['debugfs', '-R', 'cat /system/build.prop', str(root / 'raw')])
                self.assertNotIn('-w', args)
                self.assertEqual(kwargs['timeout'], 25)
                self.assertEqual(kwargs['preexec_fn'], module.limits)
                kwargs['stdout'].write(b'ro.build.version.sdk=34\n')
                return subprocess.CompletedProcess(args, 0)
            with patch.object(module.subprocess, 'run', side_effect=run):
                data, _ = module.read_debugfs(root / 'raw', 'cat /system/build.prop', root)
            self.assertIn(b'sdk=34', data)


if __name__ == '__main__':
    unittest.main()
