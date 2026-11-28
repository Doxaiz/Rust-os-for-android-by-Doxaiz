#!/usr/bin/env python3
"""Read-only booted firmware acceptance gates; never installs/starts an APK.

This is not CTS/VTS, a signature verifier, or a Redmi hardware compatibility test.
Expected identity must come from the independent build artifacts, not the device.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys


class CheckFailed(Exception):
    pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', required=True)
    parser.add_argument('--expected-version', required=True)
    parser.add_argument('--expected-fingerprint', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if not args.expected_version.strip() or not args.expected_fingerprint.strip():
        parser.error('expected build identity must not be empty')
    # Never overwrite a previous report. Keep failure evidence as well as success.
    try:
        args.output.mkdir(parents=True, mode=0o700, exist_ok=False)
    except OSError as error:
        print(f'Cannot create a NEW report directory: {error}', file=sys.stderr)
        return 1
    result = {'passed': False, 'scope': 'booted-firmware-baseline-only',
              'expected_version': args.expected_version,
              'expected_fingerprint': args.expected_fingerprint,
              'commands': [], 'checks': []}

    def adb(label, *command):
        try:
            proc = subprocess.run(['adb', '-s', args.serial, *command],
                                  capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise CheckFailed(f'{label}: {error}') from error
        (args.output / f'{label}.txt').write_text(proc.stdout, encoding='utf-8')
        (args.output / f'{label}.stderr.txt').write_text(proc.stderr, encoding='utf-8')
        result['commands'].append({'label': label, 'args': list(command), 'code': proc.returncode})
        if proc.returncode:
            raise CheckFailed(f'{label}: adb failed, exit {proc.returncode}')
        return proc.stdout.strip()

    def require(condition, message):
        result['checks'].append({'check': message, 'passed': bool(condition)})
        if not condition:
            raise CheckFailed(message)

    try:
        require(adb('state', 'get-state') == 'device', 'ADB device is online')
        require(adb('boot', 'shell', 'getprop', 'sys.boot_completed') == '1', 'Android boot completed')
        require(adb('version', 'shell', 'getprop', 'ro.doxaiz.version') == args.expected_version,
                'DoxaizOS version matches independent expected build')
        require(adb('fingerprint', 'shell', 'getprop', 'ro.build.fingerprint') == args.expected_fingerprint,
                'Fingerprint matches independent expected build')
        require(adb('lowram', 'shell', 'getprop', 'ro.config.low_ram') == 'true', 'Low-RAM profile enabled')
        require(adb('selinux', 'shell', 'getenforce') == 'Enforcing', 'SELinux enforcing')
        package_paths = adb('package', 'shell', 'pm', 'path', 'com.doxaiz.launcher').splitlines()
        require(bool(package_paths) and all(
            line.startswith(('package:/system/', 'package:/product/', 'package:/system_ext/'))
            for line in package_paths), 'Launcher is preinstalled, not only adb-installed in /data')
        home = adb('home', 'shell', 'cmd', 'package', 'resolve-activity', '--brief',
                   '-a', 'android.intent.action.MAIN', '-c', 'android.intent.category.HOME')
        require(any(line.startswith('com.doxaiz.launcher/') for line in home.splitlines()),
                'Default HOME resolves to preinstalled Launcher without reassignment')
        services = adb('services', 'shell', 'service', 'list')
        for service in ('activity', 'package', 'window'):
            require(any(line.split(':', 1)[0].split()[-1:] == [service]
                        for line in services.splitlines()), f'Core service {service} registered')
        memory = adb('meminfo', 'shell', 'cat', '/proc/meminfo')
        require('MemTotal:' in memory and 'MemAvailable:' in memory, 'Memory diagnostics available')
        adb('storage', 'shell', 'df', '-k', '/data')
        result['passed'] = True
    except CheckFailed as error:
        result['error'] = str(error)
        print(f'FAIL: {error}', file=sys.stderr)
    finally:
        (args.output / 'result.json').write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if result['passed']:
        print('PASS: firmware baseline gates only; not full OS/hardware certification')
        return 0
    return 1


if __name__ == '__main__':
    sys.exit(main())
