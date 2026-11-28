#!/usr/bin/env python3
"""Destructive-to-VM reboot/persistence test for a disposable LOCAL Cuttlefish.

Not a firmware identity verifier, CTS, performance result or hardware test.
Writes one random /data/local/tmp marker, syncs, reboots and removes the marker.
Never installs APKs, assigns HOME, roots adbd or changes system properties.
"""
import argparse
import json
from pathlib import Path
import secrets
import subprocess
import sys
import time
import uuid


class LifecycleFailed(Exception):
    pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--boot-timeout', type=int, default=300)
    parser.add_argument('--allow-disposable-reboot', action='store_true',
                        help='Explicit consent to reboot this disposable Cuttlefish only')
    args = parser.parse_args()
    if not args.allow_disposable_reboot:
        parser.error('--allow-disposable-reboot is required')
    if args.serial not in ('127.0.0.1:6520', 'localhost:6520'):
        parser.error('only local Cuttlefish ADB port 6520 is allowed')
    if not 1 <= args.boot_timeout <= 900:
        parser.error('boot-timeout must be 1..900 seconds')
    try:
        args.output.mkdir(parents=True, mode=0o700, exist_ok=False)
    except OSError as error:
        print(f'FAIL: new private report directory required: {error}', file=sys.stderr)
        return 1
    result = {'passed': False, 'scope': 'cuttlefish-reboot-persistence-only',
              'not_proven': ['DoxaizOS build provenance', 'CTS/VTS', 'Redmi compatibility',
                             'performance or memory budgets'],
              'commands': [], 'checks': [], 'optional_diagnostics': {}}
    marker = '/data/local/tmp/doxaiz-lifecycle-' + secrets.token_hex(16)
    token = secrets.token_hex(16)
    marker_created = False

    def adb(label, *command, required=True, timeout=20):
        entry = {'label': label, 'args': list(command), 'code': None}
        result['commands'].append(entry)
        try:
            proc = subprocess.run(['adb', '-s', args.serial, *command],
                                  capture_output=True, text=True, errors='replace', timeout=timeout)
            entry['code'] = proc.returncode
            (args.output / (label + '.txt')).write_text(proc.stdout)
            (args.output / (label + '.stderr.txt')).write_text(proc.stderr)
            if proc.returncode == 0:
                return proc.stdout.strip()
            error = f'{label}: adb exit {proc.returncode}'
        except (OSError, subprocess.TimeoutExpired) as failure:
            error = f'{label}: {failure}'
            entry['error'] = str(failure)
        if required:
            raise LifecycleFailed(error)
        return None

    def require(condition, message):
        result['checks'].append({'check': message, 'passed': bool(condition)})
        if not condition:
            raise LifecycleFailed(message)

    def boot_id(label, required=True, timeout=20):
        value = adb(label, 'shell', 'cat', '/proc/sys/kernel/random/boot_id',
                    required=required, timeout=timeout)
        try:
            parsed = uuid.UUID(value or '')
            if parsed.int:
                return str(parsed)
        except ValueError:
            pass
        if required:
            raise LifecycleFailed(label + ': missing/invalid kernel boot UUID')
        return None

    def services(phase):
        require(adb(phase + '-selinux', 'shell', 'getenforce') == 'Enforcing',
                phase + ': SELinux Enforcing')
        values = adb(phase + '-services', 'shell', 'service', 'list')
        for name in ('activity', 'package', 'window'):
            require(any(line.split(':', 1)[0].split()[-1:] == [name]
                        for line in values.splitlines()), phase + ': core service ' + name)

    def diagnostics(phase):
        paths = {'meminfo': '/proc/meminfo', 'swaps': '/proc/swaps',
                 'memory-pressure': '/proc/pressure/memory',
                 'zram-algorithm': '/sys/block/zram0/comp_algorithm',
                 'zram-mm-stat': '/sys/block/zram0/mm_stat',
                 'zram-disksize': '/sys/block/zram0/disksize'}
        for name, path in paths.items():
            value = adb(phase + '-' + name, 'shell', 'cat', path, required=False)
            result['optional_diagnostics'][phase + '-' + name] = 'available' if value else 'unavailable'

    try:
        hardware = adb('hardware', 'shell', 'getprop', 'ro.hardware')
        require(hardware.startswith(('cutf_', 'cuttlefish')), 'Local target reports Cuttlefish hardware')
        require(adb('before-completed', 'shell', 'getprop', 'sys.boot_completed') == '1',
                'Android boot completed before test')
        services('before')
        before_id = boot_id('before-boot-id')
        before_count = adb('before-count', 'shell', 'settings', 'get', 'global', 'boot_count')
        require(before_count.isdecimal(), 'Valid boot count before reboot')
        fingerprint = adb('before-fingerprint', 'shell', 'getprop', 'ro.build.fingerprint')
        require(bool(fingerprint), 'Nonempty fingerprint for continuity check (NOT provenance)')
        result.update(boot_id_before=before_id, boot_count_before=int(before_count),
                      observed_fingerprint=fingerprint)
        diagnostics('before')
        marker_created = True  # also clean up a partially successful write
        adb('write-marker', 'shell', f"printf '%s' '{token}' > '{marker}'")
        adb('sync', 'shell', 'sync')
        adb('reboot', 'reboot')
        deadline = time.monotonic() + args.boot_timeout
        attempt = 0
        while time.monotonic() < deadline:
            attempt += 1
            # Bound the ENTIRE wait, not just each command in the polling loop.
            def probe(label, *command):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                return adb(f'poll-{attempt:03d}-{label}', *command, required=False,
                           timeout=min(10, remaining))
            probe('connect', 'connect', args.serial)
            completed = probe('completed', 'shell', 'getprop', 'sys.boot_completed')
            after_count = probe('count', 'shell', 'settings', 'get', 'global', 'boot_count')
            remaining = deadline - time.monotonic()
            after_id = boot_id(f'poll-{attempt:03d}-boot-id', required=False,
                               timeout=min(10, remaining)) if remaining > 0 else None
            if (completed == '1' and after_count and after_count.isdecimal()
                    and int(after_count) > int(before_count) and after_id and after_id != before_id):
                result.update(boot_id_after=after_id, boot_count_after=int(after_count))
                break
            time.sleep(max(0, min(2, deadline - time.monotonic())))
        else:
            raise LifecycleFailed('No confirmed kernel reboot + increased boot count + completed Android boot')
        require(adb('read-marker', 'shell', 'cat', marker) == token,
                'Userdata marker survived reboot unchanged')
        require(adb('after-fingerprint', 'shell', 'getprop', 'ro.build.fingerprint') == fingerprint,
                'Observed fingerprint unchanged across reboot (NOT provenance)')
        services('after')
        diagnostics('after')
        result['passed'] = True
    except LifecycleFailed as error:
        result['error'] = str(error)
        print(f'FAIL: {error}', file=sys.stderr)
    finally:
        if marker_created:
            cleanup = adb('remove-marker', 'shell', 'rm', '-f', marker, required=False, timeout=5)
            result['marker_cleanup_succeeded'] = cleanup is not None
            if cleanup is None:
                result['passed'] = False
                result.setdefault('error', 'Cannot remove disposable test marker')
        (args.output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    if result['passed']:
        print('PASS: disposable Cuttlefish kernel reboot, userdata and service continuity ONLY; not full firmware acceptance')
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
