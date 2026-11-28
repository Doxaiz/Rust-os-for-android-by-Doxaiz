#!/usr/bin/env python3
"""Verify and unpack a trusted Cuttlefish bundle into a NEW private directory.

Archive paths are checked before extraction; no execution. Still only use build
outputs from trusted builders: the extracted host tools will later be executed.
"""
import argparse
import importlib.util
from pathlib import Path, PurePosixPath
import shutil
import stat
import tarfile
import tempfile
import zipfile
import xml.etree.ElementTree as ET


def bundle_module():
    spec = importlib.util.spec_from_file_location('firmware_bundle', Path(__file__).with_name('firmware-bundle.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def safe_name(name):
    path = PurePosixPath(name)
    if not name or '\\' in name or path.is_absolute() or '..' in path.parts:
        raise ValueError(f'unsafe archive path: {name!r}')
    return path


def unpack(args):
    module = bundle_module()
    module.verify(args)
    if args.output.exists() or args.output.is_symlink():
        raise ValueError('output already exists')
    # The caller specifies a disk budget. Bounds cover uncompressed content,
    # not filesystems/runtime disk growth after boot.
    budget = args.max_unpacked_gib * 1024**3
    if budget <= 0:
        raise ValueError('max-unpacked-gib must be positive')
    with zipfile.ZipFile(args.bundle / 'images.zip') as images, tarfile.open(
            args.bundle / 'cvd-host_package.tar.gz', 'r:gz') as tools:
        entries = {}
        total = 0
        for kind, members in (('zip', images.infolist()), ('tar', tools.getmembers())):
            for entry in members:
                name = entry.filename if kind == 'zip' else entry.name
                path = safe_name(name)
                if str(path) == '.':
                    continue
                if kind == 'zip':
                    mode = entry.external_attr >> 16
                    if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) and not
                                            (stat.S_ISREG(mode) or stat.S_ISDIR(mode))):
                        raise ValueError(f'non-regular ZIP entry: {name}')
                    directory = entry.is_dir()
                    size = entry.file_size
                else:
                    if not (entry.isfile() or entry.isdir() or entry.issym()):
                        raise ValueError(f'unsupported TAR entry: {name}')
                    if entry.issym():
                        # More restrictive than tarfile's data filter: allow
                        # only simple relative links without parent traversal.
                        safe_name(entry.linkname)
                    directory = entry.isdir()
                    size = entry.size
                key = str(path)
                if key in entries and not (directory and entries[key] == 'directory'):
                    raise ValueError(f'duplicate/colliding archive entry: {name}')
                entries[key] = 'directory' if directory else ('symlink' if kind == 'tar' and entry.issym() else 'file')
                total += size
        # Reject children beneath symlinks/files regardless of archive ordering.
        for name in entries:
            for parent in PurePosixPath(name).parents:
                if entries.get(str(parent), 'directory') != 'directory':
                    raise ValueError(f'archive entry beneath file/link: {name}')
        if total > budget:
            raise ValueError('unpacked content exceeds configured disk budget')
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(args.output.parent).free < total + 1024**3:
            raise ValueError('insufficient free disk (requires archive size plus 1 GiB)')
        with tempfile.TemporaryDirectory(prefix='.unpack-', dir=args.output.parent) as tmp:
            stage = Path(tmp) / 'cvd'
            stage.mkdir(mode=0o700)
            # No archive extraction API for TAR: write regular files only,
            # without ownership/setuid metadata, then create validated links
            # LAST. No archive entry is allowed beneath a file or symlink.
            images.extractall(stage)
            links = []
            for entry in tools.getmembers():
                relative = safe_name(entry.name)
                if str(relative) == '.':
                    continue
                destination = stage.joinpath(*relative.parts)
                if entry.isdir():
                    destination.mkdir(parents=True, exist_ok=True)
                elif entry.issym():
                    links.append((destination, entry.linkname))
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with tools.extractfile(entry) as source, destination.open('xb') as target:
                        shutil.copyfileobj(source, target)
                    destination.chmod(entry.mode & 0o755)
            for destination, linkname in links:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.symlink_to(linkname)
            launcher = stage / 'bin/launch_cvd'
            stopper = stage / 'bin/stop_cvd'
            for tool in (launcher, stopper):
                if not tool.is_file() or tool.is_symlink() or not tool.stat().st_mode & stat.S_IXUSR:
                    raise ValueError(f'missing/non-executable regular host tool: {tool.name}')
            if not list(stage.glob('*.img')):
                raise ValueError('no top-level image in bundle')
            stage.rename(args.output)
    print(f'UNPACKED (not booted): {args.output}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', required=True, type=Path)
    parser.add_argument('--metadata-sha256', required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--max-unpacked-gib', default=30, type=int)
    args = parser.parse_args()
    try:
        unpack(args)
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError, tarfile.TarError, zipfile.BadZipFile) as error:
        parser.exit(1, f'FAIL: {error}\n')


if __name__ == '__main__':
    main()
