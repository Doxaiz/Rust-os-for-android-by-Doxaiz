"""Synthetic artifact tests, NOT an Android build or boot."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).resolve().parents[1] / 'firmware-bundle.py'


class BundleTests(unittest.TestCase):
    def test_export_integrity_and_refusals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / 'target.zip'
            images = root / 'images.zip'
            host = root / 'host.tar.gz'
            manifest = root / 'manifest.xml'
            output = root / 'bundle'
            with zipfile.ZipFile(images, 'w') as z:
                z.writestr('system.img', b'NOT A REAL IMAGE')
            host.write_bytes(b'NOT REAL HOST TOOLS')
            manifest.write_text('<manifest><project name="fake" revision="' + 'a' * 40 + '"/></manifest>')

            def write_target(props=None, apk=True):
                with zipfile.ZipFile(target, 'w') as z:
                    z.writestr('SYSTEM/build.prop', props if props is not None else
                               'ro.build.fingerprint=synthetic/test\nro.doxaiz.version=test\nro.config.low_ram=true\n')
                    if apk:
                        z.writestr('SYSTEM/app/DoxaizLauncher/DoxaizLauncher.apk', b'fake')

            def run(*args):
                return subprocess.run(['python3', str(SCRIPT), *map(str, args)],
                                      capture_output=True, text=True, timeout=10)

            def export():
                return run('export', '--images', images, '--host-tools', host,
                           '--target-files', target, '--repo-manifest', manifest,
                           '--source-commit', 'b' * 40, '--output', output)

            write_target()
            result = export()
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads((output / 'bundle.json').read_text())
            self.assertEqual(data['expected']['version'], 'test')
            self.assertEqual(data['expected']['fingerprint'], 'synthetic/test')
            sha = hashlib.sha256((output / 'bundle.json').read_bytes()).hexdigest()

            def verify(expected=sha):
                return run('verify', '--bundle', output, '--metadata-sha256', expected)

            self.assertEqual(verify().returncode, 0)
            self.assertNotEqual(verify('0' * 64).returncode, 0)
            self.assertNotEqual(export().returncode, 0)  # no overwrite
            copied = output / 'images.zip'
            original = copied.read_bytes()
            copied.write_bytes(b'corrupt')
            self.assertNotEqual(verify().returncode, 0)
            copied.unlink()
            copied.symlink_to(images)
            self.assertNotEqual(verify().returncode, 0)
            copied.unlink()
            copied.write_bytes(original)
            self.assertEqual(verify().returncode, 0)
            for file in output.iterdir():
                file.unlink()
            output.rmdir()

            write_target(apk=False)
            self.assertNotEqual(export().returncode, 0)
            self.assertFalse(output.exists())
            write_target('ro.doxaiz.version=x\nro.config.low_ram=true\n')
            self.assertNotEqual(export().returncode, 0)  # missing fingerprint
            write_target('ro.doxaiz.version=x\nro.config.low_ram=false\nro.build.fingerprint=x\n')
            self.assertNotEqual(export().returncode, 0)
            write_target('ro.doxaiz.version=x\nro.doxaiz.version=y\nro.config.low_ram=true\nro.build.fingerprint=x\n')
            self.assertNotEqual(export().returncode, 0)
            write_target()
            manifest.write_text('<manifest><project name="fake" revision="main"/></manifest>')
            self.assertNotEqual(export().returncode, 0)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
