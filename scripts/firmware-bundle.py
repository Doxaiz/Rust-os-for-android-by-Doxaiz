#!/usr/bin/env python3
"""Export/verify a local Cuttlefish delivery bundle; never boot or flash anything.

Identity comes from build target-files, never from an already running device.
Hashes detect corruption, not a malicious builder. No build/CTS claim is made.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
import zipfile


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def identity(target_files):
    props = {}
    launcher = False
    with zipfile.ZipFile(target_files) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('duplicate target-files ZIP entries')
        for info in archive.infolist():
            if re.fullmatch(r'(SYSTEM|PRODUCT|SYSTEM_EXT)/.*DoxaizLauncher[^/]*\.apk', info.filename):
                launcher = True
            if info.filename not in ('SYSTEM/build.prop', 'SYSTEM/system/build.prop',
                                     'PRODUCT/build.prop', 'SYSTEM_EXT/build.prop',
                                     'VENDOR/build.prop', 'ODM/build.prop'):
                continue
            if info.file_size > 2 * 1024 * 1024:
                raise ValueError('oversized build.prop')
            for line in archive.read(info).decode('utf-8').splitlines():
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                key, value = key.strip(), value.strip()
                if key not in ('ro.build.fingerprint', 'ro.doxaiz.version', 'ro.config.low_ram'):
                    continue
                if key in props and props[key] != value:
                    raise ValueError(f'conflicting build property: {key}')
                props[key] = value
    if not launcher:
        raise ValueError('no preinstalled DoxaizLauncher APK entry in target-files')
    if props.get('ro.config.low_ram') != 'true':
        raise ValueError('target-files does not enable low RAM')
    for key in ('ro.build.fingerprint', 'ro.doxaiz.version'):
        if not props.get(key):
            raise ValueError(f'missing build property: {key}')
    return {'version': props['ro.doxaiz.version'],
            'fingerprint': props['ro.build.fingerprint'], 'low_ram': True}


def pinned_manifest(path):
    tree = ET.parse(path)
    projects = tree.findall('project')
    if tree.getroot().tag != 'manifest' or not projects:
        raise ValueError('repo manifest must contain projects')
    if any(not re.fullmatch(r'[0-9a-f]{40}', p.get('revision', '')) for p in projects):
        raise ValueError('use repo manifest -r: all project revisions must be pinned SHA-1')


def export(args):
    if args.output.exists():
        raise ValueError('output already exists; refusing to overwrite')
    if not re.fullmatch(r'[0-9a-f]{40}', args.source_commit):
        raise ValueError('source-commit must be a full Git SHA-1')
    expected = identity(args.target_files)
    pinned_manifest(args.repo_manifest)
    # Image archive is an opaque build output, never extracted here.
    if not zipfile.is_zipfile(args.images):
        raise ValueError('images must be a ZIP archive')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.bundle-', dir=args.output.parent) as tmp:
        stage = Path(tmp) / 'bundle'
        stage.mkdir(mode=0o700)
        artifacts = {}
        for name, source in (('images.zip', args.images),
                             ('cvd-host_package.tar.gz', args.host_tools),
                             ('repo-manifest.xml', args.repo_manifest)):
            if not source.is_file() or source.stat().st_size == 0:
                raise ValueError(f'empty or missing artifact: {source}')
            shutil.copyfile(source, stage / name)
            artifacts[name] = {'sha256': digest(stage / name),
                               'bytes': (stage / name).stat().st_size}
        metadata = {'schema': 1, 'scope': 'unbooted-cuttlefish-build-delivery',
                    'source_commit': args.source_commit, 'expected': expected,
                    'target_files_sha256': digest(args.target_files),
                    'artifacts': artifacts,
                    'limitations': ['Not signed or attested', 'Not a boot/CTS result',
                                    'Builder must supply images, tools and target-files from SAME build']}
        (stage / 'bundle.json').write_text(json.dumps(metadata, indent=2) + '\n')
        stage.rename(args.output)
    print(f'Exported {args.output}; metadata SHA-256: {digest(args.output / "bundle.json")}')


def verify(args):
    path = args.bundle / 'bundle.json'
    if path.is_symlink() or digest(path) != args.metadata_sha256:
        raise ValueError('metadata SHA-256 mismatch (or symlink)')
    metadata = json.loads(path.read_text())
    expected_names = {'images.zip', 'cvd-host_package.tar.gz', 'repo-manifest.xml'}
    if metadata.get('schema') != 1 or set(metadata.get('artifacts', {})) != expected_names:
        raise ValueError('unsupported bundle schema/artifact set')
    expected = metadata.get('expected')
    if (not isinstance(expected, dict) or expected.get('low_ram') is not True or
            any(not isinstance(expected.get(key), str) or not expected[key].strip() or
                any(ord(char) < 32 for char in expected[key])
                for key in ('version', 'fingerprint'))):
        raise ValueError('invalid expected firmware identity')
    if not re.fullmatch(r'[0-9a-f]{40}', metadata.get('source_commit', '')):
        raise ValueError('invalid source commit')
    for name in sorted(expected_names):
        artifact = args.bundle / name
        entry = metadata['artifacts'][name]
        if artifact.is_symlink() or not artifact.is_file():
            raise ValueError(f'not a regular artifact: {name}')
        if artifact.stat().st_size != entry['bytes'] or digest(artifact) != entry['sha256']:
            raise ValueError(f'artifact integrity failure: {name}')
    pinned_manifest(args.bundle / 'repo-manifest.xml')
    print('PASS: delivery hashes and pinned manifest only; NOT firmware acceptance')
    print(json.dumps(metadata['expected'], indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    create = sub.add_parser('export')
    for name in ('images', 'host-tools', 'target-files', 'repo-manifest', 'output'):
        create.add_argument('--' + name, required=True, type=Path)
    create.add_argument('--source-commit', required=True)
    check = sub.add_parser('verify')
    check.add_argument('--bundle', required=True, type=Path)
    check.add_argument('--metadata-sha256', required=True,
                       help='Expected bundle.json SHA-256 from trusted build channel, not bundle itself')
    args = parser.parse_args()
    try:
        (export if args.command == 'export' else verify)(args)
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError, zipfile.BadZipFile) as error:
        parser.exit(1, f'FAIL: {error}\n')


if __name__ == '__main__':
    main()
