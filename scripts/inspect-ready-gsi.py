#!/usr/bin/env python3
"""Read-only userspace inspection of a pinned gzip/ext4 GSI on Linux.

Uses debugfs WITHOUT -w or mounts; never executes files from the image.
Hash pin is previously OBSERVED, not publisher authentication. Untrusted FS
parsing still has risk: use only a disposable unprivileged, secret-free runner.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import resource
import subprocess
import sys
import tempfile
import zlib

LIMIT = 2 * 1024**2
PROPS = ('/build.prop', '/system/build.prop', '/system/system/build.prop')
KEY = re.compile(r'ro\.(?:build\.(?:fingerprint|version\.(?:release|sdk|security_patch))|'
                 r'system\.build\.(?:fingerprint|version\.(?:release|sdk|security_patch))|'
                 r'product\.cpu\.(?:abi|abilist|abilist32|abilist64)|'
                 r'config\.low_ram|lineage\.(?:version|build\.version)|treble\.enabled)\Z')


def parse_props(data):
    result = {}
    for line in data.decode('utf-8', errors='strict').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = (part.strip() for part in line.split('=', 1))
        if KEY.fullmatch(key):
            if key in result and result[key] != value:
                raise ValueError('conflicting property: ' + key)
            if any(ord(c) < 32 for c in value):
                raise ValueError('control character in property')
            result[key] = value
    return result


def elf_header(data):
    if len(data) < 20 or data[:4] != b'\x7fELF' or data[4] not in (1, 2) or data[5] not in (1, 2):
        return None
    return {'class_bits': 32 if data[4] == 1 else 64,
            'machine': int.from_bytes(data[18:20], 'little' if data[5] == 1 else 'big')}


def limits():
    resource.setrlimit(resource.RLIMIT_FSIZE, (LIMIT, LIMIT))
    resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def read_debugfs(raw, command, work):
    # Fixed commands only. No shell, -w, kernel mount, host extraction paths,
    # image-provided commands, libraries or executables.
    with tempfile.TemporaryFile(dir=work) as out, tempfile.TemporaryFile(dir=work) as err:
        proc = subprocess.run(['debugfs', '-R', command, str(raw)], stdout=out, stderr=err,
                              timeout=25, preexec_fn=limits)
        out.seek(0)
        data = out.read(LIMIT + 1)
        err.seek(0)
        error = err.read(LIMIT + 1)
    if len(data) >= LIMIT or len(error) >= LIMIT or proc.returncode != 0:
        raise ValueError('debugfs failed or output limit reached: ' + command)
    # debugfs may return 0 for missing files; preserve stderr and treat empty
    # output as unavailable, NOT a negative finding about installed software.
    return data, error.decode('utf-8', errors='replace')


def inspect(image, expected, output, maximum=8 * 1024**3):
    if not re.fullmatch('[0-9a-f]{64}', expected):
        raise ValueError('full lowercase SHA-256 required')
    if output.exists() or output.is_symlink():
        raise ValueError('new report directory required')
    if image.is_symlink() or not image.is_file() or not 0 < image.stat().st_size <= 2 * 1024**3:
        raise ValueError('regular compressed input <= 2 GiB required')
    output.mkdir(parents=True, mode=0o700)
    result = {'passed': False, 'scope': 'read-only-untrusted-filesystem-inspection',
              'publisher_authenticated': False, 'boot_tested': False,
              'device_compatible': None, 'properties_by_path': {}, 'elf_by_path': {},
              'diagnostics': {}, 'observed_compressed_sha256': None}
    try:
        digest = hashlib.sha256()
        with image.open('rb') as stream:
            for block in iter(lambda: stream.read(1024**2), b''):
                digest.update(block)
        result['observed_compressed_sha256'] = digest.hexdigest()
        if digest.hexdigest() != expected:
            raise ValueError('candidate differs from previously observed hash; refusing filesystem parser')
        with tempfile.TemporaryDirectory(prefix='.gsi-inspection-', dir=output.parent) as tmp:
            work = Path(tmp)
            raw = work / 'candidate.raw'
            size = 0
            with gzip.open(image, 'rb') as source, raw.open('xb') as dest:
                while True:
                    block = source.read(min(1024**2, maximum - size + 1))
                    if not block:
                        break
                    size += len(block)
                    if size > maximum:
                        raise ValueError('expanded image exceeds limit')
                    dest.write(block)
            with raw.open('rb') as stream:
                stream.seek(1080)
                if stream.read(2) != b'\x53\xef':
                    raise ValueError('only raw ext4 supported; no automatic sparse conversion')
            result['expanded_bytes'] = size
            for path in PROPS:
                data, diagnostic = read_debugfs(raw, 'cat ' + path, work)
                result['diagnostics'][path] = diagnostic
                if data:
                    (output / (path.strip('/').replace('/', '-') + '.txt')).write_bytes(data)
                    result['properties_by_path'][path] = parse_props(data)
            for path in ('/bin/app_process32', '/system/bin/app_process32',
                         '/bin/app_process64', '/system/bin/app_process64'):
                data, diagnostic = read_debugfs(raw, 'cat ' + path, work)
                result['diagnostics'][path] = diagnostic
                info = elf_header(data)
                if info:
                    result['elf_by_path'][path] = info
            for path in ('/app', '/priv-app', '/system/app', '/system/priv-app'):
                data, diagnostic = read_debugfs(raw, 'ls -p ' + path, work)
                result['diagnostics'][path] = diagnostic
                if data:
                    (output / (path.strip('/').replace('/', '-') + '-listing.txt')).write_bytes(data)
            if not any(result['properties_by_path'].values()):
                raise ValueError('no recognized system properties; inspection incomplete')
            result['passed'] = True
    except (OSError, ValueError, EOFError, zlib.error, subprocess.SubprocessError) as error:
        result['error'] = str(error)
    (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--observed-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = inspect(args.image, args.observed_sha256, args.output)
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + '\n')
    print(json.dumps(result, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
