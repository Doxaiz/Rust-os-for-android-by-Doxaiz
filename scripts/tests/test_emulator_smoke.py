"""Safety guards for smoke script. Real Android functionality is tested in CI."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'emulator-smoke.sh'
MOCK = r'''
import os, sys
with open(os.environ['CALLS'], 'a') as f:
    f.write(' '.join(sys.argv[1:]) + '\n')
if sys.argv[-1] == 'ro.kernel.qemu':
    print('1' if os.environ['CASE'] == 'install_failure' else '0')
elif 'install' in sys.argv:
    sys.exit(1)
'''


class EmulatorSmokeSafetyTests(unittest.TestCase):
    def test_guards(self):
        for mode in ('physical_serial', 'not_qemu', 'missing_apk', 'install_failure'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                bindir = root / 'bin'
                bindir.mkdir()
                adb = bindir / 'adb'
                adb.write_text('#!' + sys.executable + '\n' + MOCK)
                adb.chmod(0o755)
                apk = root / 'launcher.apk'
                if mode != 'missing_apk':
                    apk.write_bytes(b'mock')
                report = root / 'report'
                calls = root / 'calls'
                env = dict(os.environ, PATH=str(bindir) + ':' + os.environ['PATH'],
                           DOXAIZ_ADB_TARGET='physical-phone' if mode == 'physical_serial' else 'emulator-5554',
                           CASE=mode, CALLS=str(calls))
                result = subprocess.run(['bash', str(SCRIPT), str(apk), str(report)],
                                        env=env, text=True, capture_output=True, timeout=10)
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertFalse((report / 'result.txt').exists())
                trace = calls.read_text() if calls.exists() else ''
                if mode != 'install_failure':
                    self.assertNotIn('install', trace)
                    self.assertFalse(report.exists())
                if mode in ('physical_serial', 'missing_apk'):
                    self.assertFalse(calls.exists())


if __name__ == '__main__':
    unittest.main()
