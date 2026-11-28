"""Synthetic files and mocked debugfs, NOT parsing a real Android filesystem."""
import gzip
import hashlib
import importlib.util
from pathlib import Path
import subprocess
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
                    return b'', 'unavailable'
                with patch.object(module, 'read_debugfs', side_effect=reader) as debugfs:
                    result = module.inspect(image, expected, root / 'report',
                                            maximum=1 if case == 'expanded_limit' else 8192)
                self.assertEqual(result['passed'], case == 'success')
                self.assertFalse(result['publisher_authenticated'])
                self.assertFalse(result['boot_tested'])
                self.assertIsNone(result['device_compatible'])
                self.assertFalse(list(root.glob('.gsi-inspection-*')))
                if case in ('bad_hash', 'expanded_limit', 'bad_header'):
                    debugfs.assert_not_called()
                with self.assertRaises(ValueError):
                    module.inspect(image, expected, root / 'report')

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
