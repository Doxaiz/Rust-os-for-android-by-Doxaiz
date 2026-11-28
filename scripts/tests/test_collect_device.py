"""Offline tests: no Android device required, adb calls are recorded and mocked."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'collect-device.sh'
MOCK = r'''
import json, os, sys
args = sys.argv[1:]
assert args[:2] == ['-s', 'chosen-serial'], args
with open(os.environ['CALLS'], 'a') as f:
    f.write(json.dumps(args) + '\n')
args = args[2:]
mode = os.environ['CASE']
if args == ['get-state']:
    print('offline' if mode == 'offline' else 'device')
elif args == ['shell', 'getprop', 'sys.boot_completed']:
    print('0' if mode == 'booting' else '1\r')
elif args[:3] == ['shell', 'pm', 'path']:
    if mode != 'no_package':
        print('package:/system/app/DoxaizLauncher.apk')
elif args == ['shell', 'cat', '/proc/meminfo']:
    print('MemTotal: 2048000 kB\nMemAvailable: 1100000 kB')
elif args[:3] == ['shell', 'dumpsys', 'meminfo']:
    if mode == 'dump_failure':
        sys.exit(1)
    print('TOTAL PSS: 46100')
elif args[:3] == ['shell', 'dumpsys', 'gfxinfo']:
    if mode != 'empty_gfx':
        print('Total frames rendered: 100\nJanky frames: 1 (1.00%)\n90th percentile: 12ms')
elif args[:2] == ['shell', 'getprop']:
    print('synthetic-property')
else:
    raise AssertionError(args)
'''


class CollectDeviceTests(unittest.TestCase):
    def test_capture_and_failure_safety(self):
        for mode in ('success', 'offline', 'booting', 'no_package', 'dump_failure',
                     'empty_gfx', 'existing_output'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                bindir = root / 'bin'
                bindir.mkdir()
                adb = bindir / 'adb'
                adb.write_text('#!' + sys.executable + '\n' + MOCK)
                adb.chmod(0o755)
                output = root / 'reports with spaces' / 'report'
                if mode == 'existing_output':
                    output.mkdir(parents=True)
                    (output / 'keep.txt').write_text('existing report')
                calls = root / 'calls'
                env = dict(os.environ, PATH=str(bindir) + ':' + os.environ['PATH'],
                           CASE=mode, CALLS=str(calls))
                result = subprocess.run(['bash', str(SCRIPT), 'chosen-serial', str(output)],
                                        env=env, capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode == 0, mode == 'success', result.stdout + result.stderr)
                self.assertEqual(list(root.rglob('.device-report.*')), [])
                if mode == 'success':
                    self.assertEqual({p.name for p in output.iterdir()},
                                     {'context.txt', 'meminfo.txt', 'pss.txt', 'gfxinfo.txt'})
                    self.assertEqual(output.stat().st_mode & 0o777, 0o700)
                    self.assertIn('collected_at_utc=', (output / 'context.txt').read_text())
                elif mode == 'existing_output':
                    self.assertEqual((output / 'keep.txt').read_text(), 'existing report')
                    self.assertFalse(calls.exists())
                else:
                    self.assertFalse(output.exists())
                if calls.exists():
                    commands = [json.loads(line) for line in calls.read_text().splitlines()]
                    for command in commands:
                        self.assertEqual(command[:2], ['-s', 'chosen-serial'])
                        self.assertFalse({'install', 'reboot', 'root', 'force-stop', 'reset'} & set(command))


if __name__ == '__main__':
    unittest.main()
