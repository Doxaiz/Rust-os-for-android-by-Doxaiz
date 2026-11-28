"""Mocked launch/ADB only: never evidence that an image really boots."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from test_check_firmware import MOCK
from test_unpack_firmware import fixture_bundle

SCRIPTS = Path(__file__).resolve().parents[1]


class BootFirmwareBundleTests(unittest.TestCase):
    def test_boot_orchestration_and_cleanup(self):
        for case in ('success', 'wrong_version', 'wrong_home', 'existing_device', 'bad_hash', 'existing_output',
                     'stop_failure', 'after_home', 'after_version', 'reboot_failure'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                scripts = root / 'repo/scripts'
                scripts.mkdir(parents=True)
                for name in ('boot-firmware-bundle.sh', 'unpack-firmware.py', 'firmware-bundle.py', 'check-firmware.py', 'check-os-lifecycle.py'):
                    shutil.copyfile(SCRIPTS / name, scripts / name)
                # ONLY this test copy bypasses the physical KVM check. Never
                # expose a production flag for running fake hardware as real.
                script = scripts / 'boot-firmware-bundle.sh'
                script.write_text(script.read_text().replace('/dev/kvm', '/dev/null'))
                bindir = root / 'bin'
                bindir.mkdir()
                mock = bindir / 'adb'
                prefix = '''
from pathlib import Path
import os, sys
args = sys.argv[1:]
if args[:1] in (['start-server'], ['connect'], ['disconnect']):
    raise SystemExit(0)
if args[:2] == ['-s', '127.0.0.1:6520']:
    args = args[2:]
if args == ['get-state']:
    if not Path(os.environ['LAUNCHED']).exists() and os.environ['CASE'] != 'existing_device':
        raise SystemExit(1)
if args[:1] == ['logcat'] or args[:1] == ['connect']:
    raise SystemExit(0)
import re
state = Path(os.environ['LAUNCHED']).with_suffix('.rebooted')
marker = state.with_suffix('.marker')
def answer(value):
    print(value)
    raise SystemExit(0)
if args == ['shell', 'getprop', 'ro.hardware']: answer('cutf_cvm')
if args == ['shell', 'cat', '/proc/sys/kernel/random/boot_id']:
    answer('11111111-1111-1111-1111-111111111112' if state.exists() else '11111111-1111-1111-1111-111111111111')
if args == ['shell', 'settings', 'get', 'global', 'boot_count']: answer('2' if state.exists() else '1')
if args == ['reboot']:
    if os.environ['CASE'] == 'reboot_failure': raise SystemExit(1)
    state.touch()
    raise SystemExit(0)
if len(args) == 2 and args[0] == 'shell' and args[1].startswith("printf '%s'"):
    marker.write_text(re.search(r"printf '%s' '([a-f0-9]+)'", args[1]).group(1))
    raise SystemExit(0)
if args[:2] == ['shell', 'cat'] and args[2].startswith('/data/local/tmp/doxaiz-lifecycle-'):
    answer(marker.read_text())
if args[:3] == ['shell', 'rm', '-f']:
    marker.unlink()
    raise SystemExit(0)
if args == ['shell', 'sync']: raise SystemExit(0)
if args[:2] == ['shell', 'cat'] and (args[2].startswith('/sys/') or args[2] in ('/proc/swaps', '/proc/pressure/memory')):
    answer('synthetic diagnostics')
if state.exists() and os.environ['CASE'] == 'after_home' and args[:4] == ['shell', 'cmd', 'package', 'resolve-activity']:
    answer('com.android.launcher/.Home')
if state.exists() and os.environ['CASE'] == 'after_version' and args == ['shell', 'getprop', 'ro.doxaiz.version']:
    answer('changed-version')
sys.argv = [sys.argv[0], '-s', 'selected-test-device', *args]
'''
                mock.write_text('#!' + sys.executable + '\n' + prefix + MOCK)
                mock.chmod(0o755)
                bundle, sha = fixture_bundle(root)
                # Replace the tiny trusted tools with scripts recording launch/stop.
                import io
                import tarfile
                import hashlib
                host = bundle / 'cvd-host_package.tar.gz'
                with tarfile.open(host, 'w:gz') as archive:
                    for tool, marker in (('launch_cvd', 'LAUNCHED'), ('stop_cvd', 'STOPPED')):
                        payload = f'#!/bin/sh\ntouch "${marker}"\n'.encode()
                        if case == 'stop_failure' and tool == 'stop_cvd':
                            payload += b'exit 1\n'
                        entry = tarfile.TarInfo('bin/' + tool)
                        entry.mode = 0o755
                        entry.size = len(payload)
                        archive.addfile(entry, io.BytesIO(payload))
                metadata = json.loads((bundle / 'bundle.json').read_text())
                metadata['artifacts'][host.name] = {'sha256': hashlib.sha256(host.read_bytes()).hexdigest(), 'bytes': host.stat().st_size}
                (bundle / 'bundle.json').write_text(json.dumps(metadata))
                sha = hashlib.sha256((bundle / 'bundle.json').read_bytes()).hexdigest()
                output = root / 'reports'
                if case == 'existing_output':
                    output.mkdir()
                env = dict(os.environ, PATH=str(bindir) + ':' + os.environ['PATH'],
                           CASE=case, LAUNCHED=str(root / 'launched'), STOPPED=str(root / 'stopped'))
                result = subprocess.run(['bash', str(script), str(bundle),
                                         '0' * 64 if case == 'bad_hash' else sha, str(output)],
                                        capture_output=True, text=True, env=env, timeout=15)
                self.assertEqual(result.returncode == 0, case == 'success', result.stdout + result.stderr)
                started = case in ('success', 'wrong_version', 'wrong_home', 'stop_failure',
                                   'after_home', 'after_version', 'reboot_failure')
                self.assertEqual((root / 'launched').exists(), started)
                self.assertEqual((root / 'stopped').exists(), started)
                if started:
                    data = json.loads((output / 'firmware-gates/result.json').read_text())
                    self.assertEqual(data['passed'], case not in ('wrong_version', 'wrong_home'))
                    after = output / 'firmware-gates-after-reboot/result.json'
                    if case in ('success', 'stop_failure', 'after_home', 'after_version'):
                        after_result = json.loads(after.read_text())
                        self.assertEqual(after_result['passed'], case in ('success', 'stop_failure'))
                        if case == 'after_home':
                            self.assertEqual(after_result['error'], 'Default HOME resolves to preinstalled Launcher without reassignment')
                        if case == 'after_version':
                            self.assertEqual(after_result['error'], 'DoxaizOS version matches independent expected build')
                        self.assertTrue(json.loads((output / 'lifecycle/result.json').read_text())['passed'])
                    elif case == 'reboot_failure':
                        self.assertFalse(after.exists())
                        self.assertFalse(json.loads((output / 'lifecycle/result.json').read_text())['passed'])
                    else:
                        self.assertFalse((output / 'lifecycle').exists())
                    self.assertIn('exit_code=', (output / 'outcome.txt').read_text())
                    self.assertEqual((output / 'cleanup.txt').read_text().strip(),
                                     'stop_exit_code=1' if case == 'stop_failure' else 'stop_exit_code=0')


if __name__ == '__main__':
    unittest.main()
