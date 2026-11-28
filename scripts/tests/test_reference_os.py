"""Offline orchestration tests only; never evidence of a real OS boot."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "reference-os-test.sh"
FAKE_ADB = r'''#!/usr/bin/env python3
import os, pathlib, sys
args = sys.argv[1:]
state = pathlib.Path(os.environ['STATE'])
if args[:1] == ['-s']:
    args = args[2:]
cmd = ' '.join(args)
if cmd == 'shell getprop ro.hardware': print(os.environ.get('HARDWARE', 'cutf_cvm'))
elif cmd == 'shell getprop sys.boot_completed': print('1')
elif cmd == 'shell getenforce': print(os.environ.get('SELINUX', 'Enforcing'))
elif cmd == 'shell service list':
    print('0 activity: [x]\n1 package: [x]\n2 window: [x]')
elif cmd == 'shell settings get global boot_count': print('2' if state.exists() else '1')
elif cmd == 'reboot': state.touch()
elif cmd == 'shell cat /data/local/tmp/doxaiz-lab-persistence': print(os.environ.get('MARKER', 'doxaiz-lab-42'))
'''


class ReferenceOSTest(unittest.TestCase):
    def run_case(self, **changes):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = root / 'bin'
            binary.mkdir()
            adb = binary / 'adb'
            adb.write_text(FAKE_ADB)
            adb.chmod(0o755)
            env = dict(os.environ, PATH=f'{binary}:{os.environ["PATH"]}',
                       ANDROID_SERIAL='127.0.0.1:6520', GITHUB_RUN_ID='42',
                       STATE=str(root / 'rebooted'))
            env.update(changes)
            result = subprocess.run(['bash', str(SCRIPT)], cwd=root, env=env,
                                    capture_output=True, text=True, timeout=10)
            report = root / 'reports/cuttlefish-reference/result.txt'
            return result, report.read_text() if report.exists() else None

    def test_reference_flow(self):
        result, report = self.run_case()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('NOT DoxaizOS', report)
        self.assertIn('boot_count_after=2', report)

    def test_refuse_other_targets(self):
        for env in ({'ANDROID_SERIAL': 'phone'}, {'HARDWARE': 'mt6765'},
                    {'SELINUX': 'Permissive'}, {'MARKER': 'lost'}):
            with self.subTest(env=env):
                result, report = self.run_case(**env)
                self.assertNotEqual(result.returncode, 0)
                self.assertIsNone(report)


if __name__ == '__main__':
    unittest.main()
