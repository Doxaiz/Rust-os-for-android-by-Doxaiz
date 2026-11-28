"""Synthetic header tests, not an Android filesystem or boot."""
import gzip
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'audit-ready-gsi.py'
spec = importlib.util.spec_from_file_location('ready_gsi', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReadyGSITests(unittest.TestCase):
    def test_container_audit_and_limits(self):
        ext4 = bytearray(4096)
        ext4[1080:1082] = b'\x53\xef'
        sparse = struct.pack('<I4H4I', 0xed26ff3a, 1, 0, 28, 12, 4096, 2, 1, 0)
        cases = [('ext4', bytes(ext4), 8192, True), ('sparse', sparse, 8192, True),
                 ('sparse_large', sparse, 4096, False), ('unknown', b'html error', 8192, False),
                 ('expanded_large', bytes(ext4), 1024, False)]
        for name, data, maximum, expected in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                image = root / 'image.gz'
                image.write_bytes(gzip.compress(data))
                result = module.audit(image, root / 'result', 65536, maximum)
                self.assertEqual(result['passed'], expected)
                self.assertFalse(result['publisher_authenticated'])
                self.assertFalse(result['boot_tested'])
                self.assertIsNone(result['device_compatible'])
                self.assertEqual(json.loads((root / 'result/result.json').read_text()), result)
                self.assertEqual((root / 'result').stat().st_mode & 0o777, 0o700)
                with self.assertRaises(ValueError):
                    module.audit(image, root / 'result', 65536, maximum)

    def test_corrupt_crc_truncation_and_input_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = bytearray(4096)
            data[1080:1082] = b'\x53\xef'
            compressed = gzip.compress(data)
            for name, content in [('crc', compressed[:-8] + b'badcrc!!'),
                                  ('truncated', compressed[:-6]), ('not_gzip', b'not gzip')]:
                image = root / (name + '.gz')
                image.write_bytes(content)
                self.assertFalse(module.audit(image, root / name, 65536, 8192)['passed'])
            with self.assertRaises(ValueError):
                module.audit(image, root / 'too_large', 1, 8192)
            link = root / 'link.gz'
            link.symlink_to(image)
            with self.assertRaises(ValueError):
                module.audit(link, root / 'link_result', 65536, 8192)


if __name__ == '__main__':
    unittest.main()
