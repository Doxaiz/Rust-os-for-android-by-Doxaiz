"""Negative/positive orchestration tests; fixtures do NOT represent a real firmware boot."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'check-firmware.py'
MOCK = r'''
import os, sys
args = sys.argv[1:]
assert args[:2] == ['-s', 'selected-test-device']
args = args[2:]
case = os.environ['CASE']
if case == 'adb_failure':
    sys.exit(1)
if args == ['get-state']:
    print('device')
elif args[:2] == ['shell', 'getprop']:
    values = {'sys.boot_completed': '0' if case == 'booting' else '1',
              'ro.doxaiz.version': 'MIUI' if case == 'wrong_version' else '0.1.0',
              'ro.build.fingerprint': 'other-build' if case == 'wrong_fingerprint' else 'expected-build',
              'ro.config.low_ram': 'false' if case == 'wrong_profile' else 'true'}
    print(values[args[2]])
elif args == ['shell', 'getenforce']:
    print('Permissive' if case == 'permissive' else 'Enforcing')
elif args[:3] == ['shell', 'pm', 'path']:
    if case != 'no_package':
        print('package:/data/app/launcher/base.apk' if case == 'user_apk' else 'package:/system/app/DoxaizLauncher/DoxaizLauncher.apk')
elif args[:4] == ['shell', 'cmd', 'package', 'resolve-activity']:
    print('com.android.launcher/.Home' if case == 'wrong_home' else 'com.doxaiz.launcher/.MainActivity')
elif args == ['shell', 'service', 'list']:
    print('0 activity: [android.app.IActivityManager]\n1 package: [android.content.pm.IPackageManager]')
    if case != 'missing_service':
        print('2 window: [android.view.IWindowManager]')
elif args == ['shell', 'cat', '/proc/meminfo']:
    print('bad-data' if case == 'bad_meminfo' else 'MemTotal: 2048000 kB\nMemAvailable: 1000000 kB')
elif args == ['shell', 'df', '-k', '/data']:
    print('Filesystem 1K-blocks Used Available Use% Mounted on\nmock 10000 1000 9000 10% /data')
else:
    raise AssertionError('unexpected or mutating command: ' + repr(args))
'''


class FirmwareCheckTests(unittest.TestCase):
    def test_firmware_gates(self):
        for case in ('success', 'wrong_version', 'wrong_fingerprint', 'wrong_profile',
                     'permissive', 'user_apk', 'no_package', 'wrong_home',
                     'missing_service', 'booting', 'adb_failure', 'bad_meminfo', 'existing_report'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                bindir = root / 'bin'
                bindir.mkdir()
                mock = bindir / 'adb'
                mock.write_text('#!' + sys.executable + '\n' + MOCK)
                mock.chmod(0o755)
                report = root / 'reports' / 'boot'
                if case == 'existing_report':
                    report.mkdir(parents=True)
                    (report / 'keep').write_text('keep')
                env = dict(os.environ, PATH=str(bindir) + ':' + os.environ['PATH'], CASE=case)
                proc = subprocess.run([sys.executable, str(SCRIPT), '--serial', 'selected-test-device',
                                       '--expected-version', '0.1.0', '--expected-fingerprint', 'expected-build',
                                       '--output', str(report)], env=env, capture_output=True, text=True, timeout=15)
                self.assertEqual(proc.returncode == 0, case == 'success', proc.stdout + proc.stderr)
                if case == 'existing_report':
                    self.assertFalse((report / 'result.json').exists())
                    self.assertEqual((report / 'keep').read_text(), 'keep')
                else:
                    result = json.loads((report / 'result.json').read_text())
                    self.assertEqual(result['passed'], case == 'success')
                    self.assertEqual(report.stat().st_mode & 0o777, 0o700)
                    for command in result['commands']:
                        self.assertFalse({'install', 'set-home-activity', 'reboot', 'root', 'flash', 'force-stop'}
                                         & set(command['args']))


if __name__ == '__main__':
    unittest.main()
