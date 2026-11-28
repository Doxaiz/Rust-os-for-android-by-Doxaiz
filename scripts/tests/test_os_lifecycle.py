"""Synthetic ADB/clock tests only; never evidence of a real kernel boot."""
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'check-os-lifecycle.py'
spec = importlib.util.spec_from_file_location('lifecycle', SCRIPT)
lifecycle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lifecycle)


class FakeClock:
    def __init__(self):
        self.value = 0

    def now(self):
        self.value += 0.01
        return self.value

    def sleep(self, seconds):
        self.value += seconds


class FakeADB:
    def __init__(self, case):
        self.case = case
        self.rebooted = False
        self.marker = ''
        self.commands = []
        self.polls = 0

    def __call__(self, command, **kwargs):
        assert command[:3] == ['adb', '-s', '127.0.0.1:6520']
        assert 0 < kwargs['timeout'] <= 20
        args = command[3:]
        self.commands.append(args)
        code, value = 0, ''
        if args == ['shell', 'getprop', 'ro.hardware']:
            value = 'mt6765' if self.case == 'phone' else 'cutf_cvm'
        elif args == ['shell', 'getprop', 'sys.boot_completed']:
            value = '0' if self.case == 'not_booted' or (self.rebooted and self.case == 'never_boots') else '1'
            if self.rebooted and self.case == 'transport_recovery':
                self.polls += 1
                if self.polls == 1:
                    code, value = 1, ''
        elif args == ['shell', 'getenforce']:
            value = 'Permissive' if self.rebooted and self.case == 'after_selinux' else 'Enforcing'
        elif args == ['shell', 'service', 'list']:
            value = '0 activity: [x]\n1 package: [x]\n'
            if not (self.rebooted and self.case == 'after_service'):
                value += '2 window: [x]\n'
        elif args == ['shell', 'cat', '/proc/sys/kernel/random/boot_id']:
            value = '11111111-1111-1111-1111-111111111111'
            if self.rebooted and self.case != 'same_boot':
                value = '11111111-1111-1111-1111-111111111112'
            if self.case == 'invalid_boot_id':
                value = 'not-a-uuid'
        elif args == ['shell', 'settings', 'get', 'global', 'boot_count']:
            value = '5' if self.rebooted and self.case != 'same_count' else '4'
        elif args == ['shell', 'getprop', 'ro.build.fingerprint']:
            value = 'other-image' if self.rebooted and self.case == 'fingerprint_changed' else 'observed-reference'
        elif args == ['reboot']:
            self.rebooted = True
            if self.case == 'reboot_failure':
                code = 1
        elif args[:1] == ['connect'] or args == ['shell', 'sync']:
            pass
        elif args[0] == 'shell' and len(args) == 2 and args[1].startswith("printf '%s'"):
            self.marker = re.search(r"printf '%s' '([0-9a-f]+)'", args[1]).group(1)
        elif args[:2] == ['shell', 'cat'] and args[2].startswith('/data/local/tmp/doxaiz-lifecycle-'):
            value = 'lost' if self.case == 'marker_lost' else self.marker
        elif args[:3] == ['shell', 'rm', '-f']:
            if self.case == 'cleanup_failure':
                code = 1
        elif args[:2] == ['shell', 'cat']:
            if self.case == 'optional_missing':
                code = 1
            else:
                value = 'synthetic diagnostics'
        else:
            raise AssertionError('Unexpected/mutating ADB command: ' + repr(args))
        return subprocess.CompletedProcess(command, code, value, 'mock failure' if code else '')


class OSLifecycleTests(unittest.TestCase):
    def test_lifecycle_failures_and_transport_recovery(self):
        for case in ('success', 'transport_recovery', 'phone', 'not_booted', 'invalid_boot_id',
                     'reboot_failure', 'same_boot', 'same_count', 'never_boots', 'marker_lost',
                     'fingerprint_changed', 'after_selinux', 'after_service', 'optional_missing',
                     'cleanup_failure'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp) / 'report'
                adb = FakeADB(case)
                clock = FakeClock()
                argv = [str(SCRIPT), '--serial', '127.0.0.1:6520', '--output', str(output),
                        '--allow-disposable-reboot', '--boot-timeout', '3']
                with patch.object(sys, 'argv', argv), patch.object(lifecycle.subprocess, 'run', adb), \
                        patch.object(lifecycle.time, 'monotonic', clock.now), \
                        patch.object(lifecycle.time, 'sleep', clock.sleep):
                    code = lifecycle.main()
                success = case in ('success', 'transport_recovery', 'optional_missing')
                self.assertEqual(code == 0, success)
                report = json.loads((output / 'result.json').read_text())
                self.assertEqual(report['passed'], success)
                self.assertEqual(output.stat().st_mode & 0o777, 0o700)
                self.assertIn('cuttlefish-reboot-persistence-only', report['scope'])
                rebooted = case not in ('phone', 'not_booted', 'invalid_boot_id')
                self.assertEqual(['reboot'] in adb.commands, rebooted)
                if rebooted:
                    self.assertTrue(any(c[:3] == ['shell', 'rm', '-f'] for c in adb.commands))
                if success:
                    self.assertNotEqual(report['boot_id_before'], report['boot_id_after'])
                    self.assertGreater(report['boot_count_after'], report['boot_count_before'])
                if case == 'optional_missing':
                    self.assertTrue(all(v == 'unavailable' for v in report['optional_diagnostics'].values()))
                forbidden = {'install', 'root', 'set-home-activity', 'flash', 'setprop'}
                self.assertFalse(any(forbidden & set(c) for c in adb.commands))

    def test_consent_serial_and_existing_report_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'report'
            base = [str(SCRIPT), '--serial', '127.0.0.1:6520', '--output', str(output)]
            for extra, serial in (([], '127.0.0.1:6520'), (['--allow-disposable-reboot'], 'phone')):
                argv = base.copy()
                argv[2] = serial
                with patch.object(sys, 'argv', argv + extra), patch.object(lifecycle.subprocess, 'run') as adb:
                    with self.assertRaises(SystemExit):
                        lifecycle.main()
                    adb.assert_not_called()
                self.assertFalse(output.exists())
            output.mkdir()
            (output / 'keep').write_text('old evidence')
            with patch.object(sys, 'argv', base + ['--allow-disposable-reboot']), \
                    patch.object(lifecycle.subprocess, 'run') as adb:
                self.assertEqual(lifecycle.main(), 1)
                adb.assert_not_called()
            self.assertEqual((output / 'keep').read_text(), 'old evidence')


if __name__ == '__main__':
    unittest.main()
