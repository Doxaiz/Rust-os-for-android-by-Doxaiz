"""HOME configuration + mocked integration tests, not an Android boot."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
ADB = r'''
import json, os, pathlib, sys
args = sys.argv[1:]
assert args[:2] == ['-s', '127.0.0.1:6520']
args = args[2:]
root = pathlib.Path(os.environ['MOCK_STATE'])
case = os.environ['CASE']
with (root / 'calls.jsonl').open('a') as stream: stream.write(json.dumps(args) + '\n')
count_file = root / 'bootcount'
count = int(count_file.read_text()) if count_file.exists() else 1
stock = 'com.android.launcher3/.uioverrides.QuickstepLauncher'
if args[:2] == ['shell', 'getprop']:
    print({'ro.hardware': 'mt6765' if case == 'phone' else 'cutf_cvm',
           'ro.build.type': 'user' if case == 'user_build' else 'userdebug',
           'sys.boot_completed': '1'}[args[2]])
elif args == ['shell', 'id', '-u']: print('0')
elif args == ['shell', 'settings', 'get', 'global', 'boot_count']: print(count)
elif args[:3] == ['shell', 'settings', '--user']: print('1')
elif args[:2] == ['shell', 'wm']: pass
elif args[:3] == ['shell', 'dumpsys', 'package']: print('mock preferences')
elif args[:3] == ['shell', 'cmd', 'role']: pass
elif args[:4] == ['shell', 'cmd', 'package', 'query-activities']: print('priority=0 a com.doxaiz.launcher/.MainActivity\npriority=0 b com.android.launcher3/.uioverrides.QuickstepLauncher')
elif args[:2] == ['shell', 'cat']: print('mock XML')
elif args == ['reboot']: count_file.write_text(str(count + 1))
elif args == ['root'] or args == ['disable-verity']: print('mock ok')
elif args == ['remount']:
    if case == 'remount_failure': sys.exit(1)
    print('mock remount')
elif args[:1] == ['push']:
    assert pathlib.Path(args[1]).is_file()
elif args[:3] == ['shell', 'cmd', 'package'] and args[3] == 'resolve-activity':
    if '--user' not in args: print(stock)
    elif case == 'unexpected_initial_choice': print('com.doxaiz.launcher/.MainActivity')
    elif (root / 'choice').exists() and not (case == 'lost_choice' and count >= 5): print((root / 'choice').read_text())
    else: print('android/com.android.internal.app.ResolverActivity')
elif args[:4] == ['shell', 'cmd', 'package', 'set-home-activity']:
    assert args[args.index('--user') + 1] == '10'  # NEVER primary user
    (root / 'choice').write_text(args[-1])
elif args[:4] == ['shell', 'pm', 'path', 'com.doxaiz.launcher']:
    print('package:/system/app/DoxaizLauncher/DoxaizLauncher.apk')
elif args[:3] == ['shell', 'pm', 'create-user']: print('Success: created user id 10')
elif args[:3] == ['shell', 'pm', 'remove-user']:
    assert args[-1] == '10'
    (root / 'removed').touch()
elif args[:2] == ['shell', 'getenforce']: print('Enforcing')
elif args[:1] == ['logcat']: pass
elif args[:2] == ['shell', 'am']: pass
elif args[:2] in (['shell', 'mkdir'], ['shell', 'chmod'], ['shell', 'restorecon']): pass
elif args == ['shell', 'sync']: pass
else: raise AssertionError(args)
'''


class HomePolicyTests(unittest.TestCase):
    def test_xml_and_product_wiring(self):
        vendor = ROOT / 'overlay/vendor/doxaiz'
        policy = ET.parse(vendor / 'etc/preferred-apps/doxaiz-home.xml').getroot()
        self.assertEqual(policy.tag, 'preferred-activities')
        items = policy.findall('item')
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].get('name'), 'com.doxaiz.launcher/com.doxaiz.launcher.MainActivity')
        self.assertEqual([e.get('name') for e in items[0].findall('filter/action')], ['android.intent.action.MAIN'])
        self.assertEqual({e.get('name') for e in items[0].findall('filter/cat')},
                         {'android.intent.category.HOME', 'android.intent.category.DEFAULT'})
        self.assertNotIn('vendor/doxaiz/etc/preferred-apps/doxaiz-home.xml:$(TARGET_COPY_OUT_SYSTEM)/etc/preferred-apps/doxaiz-home.xml',
                      (vendor / 'products/doxaiz_base.mk').read_text())

    def test_integration_orchestration_and_guards(self):
        for case in ('success', 'outside_hosted', 'wrong_serial', 'phone', 'user_build',
                     'remount_failure', 'unexpected_initial_choice', 'lost_choice'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                repo = root / 'repo'
                (repo / 'scripts').mkdir(parents=True)
                # Avoid a real 45-second role wait in the failure fixtures.
                script = (ROOT / 'scripts/test-home-policy.sh').read_text().replace(
                    'home_deadline=$((SECONDS + 45))', 'home_deadline=$((SECONDS + 0))')
                (repo / 'scripts/test-home-policy.sh').write_text(script)
                shutil.copytree(ROOT / 'overlay', repo / 'overlay')
                (repo / 'scripts/fetch-launcher-apk.sh').write_text('''#!/bin/bash
set -eu
root="$(cd "$(dirname "$0")/.." && pwd)"
printf fixture > "$root/overlay/vendor/doxaiz/apps/DoxaizLauncher/DoxaizLauncher.apk"
''')
                bindir = root / 'bin'
                bindir.mkdir()
                adb = bindir / 'adb'
                adb.write_text('#!' + sys.executable + '\n' + ADB)
                adb.chmod(0o755)
                env = dict(os.environ, PATH=str(bindir) + ':' + os.environ['PATH'],
                           GITHUB_ACTIONS='true', RUNNER_ENVIRONMENT='github-hosted',
                           ANDROID_SERIAL='127.0.0.1:6520', CASE=case, MOCK_STATE=str(root))
                if case == 'outside_hosted': env['RUNNER_ENVIRONMENT'] = 'self-hosted'
                if case == 'wrong_serial': env['ANDROID_SERIAL'] = 'phone'
                result = subprocess.run(['bash', str(repo / 'scripts/test-home-policy.sh')],
                                        env=env, capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode == 0, case == 'success', result.stdout + result.stderr)
                report = repo / 'reports/home-policy'
                self.assertEqual((report / 'result.txt').exists(), case == 'success')
                calls = root / 'calls.jsonl'
                if case in ('outside_hosted', 'wrong_serial'):
                    self.assertFalse(calls.exists())
                elif case in ('phone', 'user_build'):
                    self.assertTrue(all(json.loads(line)[:2] == ['shell', 'getprop'] for line in calls.read_text().splitlines()))
                if case in ('success', 'unexpected_initial_choice', 'lost_choice'):
                    self.assertTrue((root / 'removed').exists())


if __name__ == '__main__':
    unittest.main()
