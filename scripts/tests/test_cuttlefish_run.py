"""Offline orchestration tests; these do not boot Cuttlefish or execute Android."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'cuttlefish-run.sh'
MOCK = r'''
import os, pathlib, sys
args = sys.argv[1:]
mode = os.environ['CASE']
with open(os.environ['CALLS'], 'a') as log:
    log.write(' '.join(args) + '\n')
if 'getprop' in args:
    print('0' if mode == 'timeout' else '1\r')
elif 'install' in args:
    sys.exit(1 if mode == 'install_failure' else 0)
elif 'path' in args:
    if mode != 'missing_package':
        print('package:/system/app/DoxaizLauncher.apk')
elif 'set-home-activity' in args:
    sys.exit(1 if mode == 'home_failure' else 0)
elif 'resolve-activity' in args:
    print('com.android.launcher/.Home' if mode == 'wrong_home' else 'com.doxaiz.launcher/.MainActivity')
elif '/proc/meminfo' in args:
    print('MemTotal: 2048000 kB\nMemAvailable: 900000 kB')
'''


class CuttlefishRunTests(unittest.TestCase):
    def test_orchestration(self):
        for mode in ('success', 'prebuilt', 'timeout', 'missing_package',
                     'install_failure', 'home_failure', 'wrong_home', 'invalid_timeout'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                bindir = root / 'bin'
                bindir.mkdir()
                for cmd in ('bash', 'dirname', 'tr', 'grep', 'sed', 'sleep'):
                    (bindir / cmd).symlink_to(shutil.which(cmd))
                adb = bindir / 'adb'
                adb.write_text('#!' + sys.executable + '\n' + MOCK)
                adb.chmod(0o755)
                launch = bindir / 'launch_cvd'
                launch.write_text('#!/bin/bash\necho launch >> "$CALLS"\n')
                launch.chmod(0o755)
                apk = root / 'launcher.apk'
                if mode not in ('prebuilt', 'missing_package'):
                    apk.write_bytes(b'fake apk for mocked adb')
                calls = root / 'calls'
                env = dict(os.environ, PATH=str(bindir), CASE=mode, CALLS=str(calls),
                           DOXAIZ_BOOT_TIMEOUT='bad' if mode == 'invalid_timeout' else '0',
                           DOXAIZ_ADB_TARGET='emulator-test:6520')
                result = subprocess.run([str(bindir / 'bash'), str(SCRIPT), str(apk)],
                                        env=env, capture_output=True, text=True, timeout=10)
                success = mode in ('success', 'prebuilt')
                self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
                trace = calls.read_text() if calls.exists() else ''
                if mode == 'invalid_timeout':
                    self.assertEqual(trace, '')
                elif mode == 'timeout':
                    self.assertNotIn('install', trace)
                    self.assertNotIn('set-home-activity', trace)
                if success:
                    self.assertIn('resolve-activity', trace)
                    self.assertIn('=== Готово.', result.stdout)
                else:
                    self.assertNotIn('=== Готово.', result.stdout)
                if mode == 'missing_package':
                    self.assertNotIn('set-home-activity', trace)
                if mode == 'prebuilt':
                    self.assertNotIn('install', trace)


if __name__ == '__main__':
    unittest.main()
