"""Adversarial synthetic archives only; no real Android artifacts."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
import zipfile

SCRIPTS = Path(__file__).resolve().parents[1]


def fixture_bundle(root, case='good'):
    bundle = root / 'bundle'
    bundle.mkdir()
    with zipfile.ZipFile(bundle / 'images.zip', 'w') as archive:
        archive.writestr('../escaped.img' if case == 'zip_traversal' else 'system.img', b'fake image')
        if case == 'collision':
            archive.writestr('bin/launch_cvd', b'collision')
        if case == 'zip_link':
            entry = zipfile.ZipInfo('link')
            entry.external_attr = 0o120777 << 16
            archive.writestr(entry, 'system.img')
    with tarfile.open(bundle / 'cvd-host_package.tar.gz', 'w:gz') as archive:
        for name in ('bin/launch_cvd', 'bin/stop_cvd'):
            entry = tarfile.TarInfo(name)
            payload = b'#!/bin/sh\nexit 0\n'
            entry.mode = 0o644 if case == 'no_exec' else 0o755
            entry.size = len(payload)
            if case == 'good_link' and name == 'bin/launch_cvd':
                entry.name = 'bin/real_launcher'
                archive.addfile(entry, io.BytesIO(payload))
                link = tarfile.TarInfo(name)
                link.type = tarfile.SYMTYPE
                link.linkname = 'real_launcher'
                archive.addfile(link)
            else:
                archive.addfile(entry, io.BytesIO(payload))
        if case in ('tar_traversal', 'tar_absolute', 'tar_link', 'tar_child', 'hardlink', 'fifo'):
            name = {'tar_traversal': '../escape', 'tar_absolute': '/escape'}.get(case, 'link')
            entry = tarfile.TarInfo(name)
            if case in ('tar_link', 'tar_child'):
                entry.type = tarfile.SYMTYPE
                entry.linkname = '../../outside' if case == 'tar_link' else 'bin'
            if case == 'hardlink':
                entry.type = tarfile.LNKTYPE
                entry.linkname = 'bin/launch_cvd'
            if case == 'fifo':
                entry.type = tarfile.FIFOTYPE
            archive.addfile(entry)
            if case == 'tar_child':
                entry = tarfile.TarInfo('link/child')
                archive.addfile(entry)
    (bundle / 'repo-manifest.xml').write_text('<manifest><project name="fake" revision="' + 'a' * 40 + '"/></manifest>')
    data = {'schema': 1, 'source_commit': 'b' * 40,
            'expected': {'version': '0.1.0', 'fingerprint': 'expected-build', 'low_ram': True},
            'artifacts': {}}
    for name in ('images.zip', 'cvd-host_package.tar.gz', 'repo-manifest.xml'):
        content = (bundle / name).read_bytes()
        data['artifacts'][name] = {'sha256': hashlib.sha256(content).hexdigest(), 'bytes': len(content)}
    (bundle / 'bundle.json').write_text(json.dumps(data))
    return bundle, hashlib.sha256((bundle / 'bundle.json').read_bytes()).hexdigest()


class UnpackFirmwareTests(unittest.TestCase):
    def test_valid_and_adversarial_archives(self):
        for case in ('good', 'good_link', 'zip_traversal', 'zip_link', 'collision', 'tar_traversal',
                     'tar_absolute', 'tar_link', 'tar_child', 'hardlink', 'fifo', 'no_exec', 'budget'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                bundle, sha = fixture_bundle(root, case)
                output = root / 'unpacked'
                result = subprocess.run(['python3', str(SCRIPTS / 'unpack-firmware.py'),
                                         '--bundle', str(bundle), '--metadata-sha256', sha,
                                         '--output', str(output), '--max-unpacked-gib',
                                         '0' if case == 'budget' else '1'],
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode == 0, case in ('good', 'good_link'), result.stdout + result.stderr)
                if case in ('good', 'good_link'):
                    self.assertEqual((output / 'system.img').read_bytes(), b'fake image')
                    self.assertTrue((output / 'bin/launch_cvd').stat().st_mode & 0o100)
                else:
                    self.assertFalse(output.exists())
                self.assertFalse((root / 'escape').exists())
                self.assertFalse((root / 'escaped.img').exists())


if __name__ == '__main__':
    unittest.main()
