#!/usr/bin/env python3
"""Bounded, offline container audit of an UNTRUSTED ready GSI; never flash/boot.

Computes observed hashes, checks gzip CRC and a minimal ext4/sparse header.
Does NOT authenticate publisher, validate a filesystem or certify compatibility.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct
import sys
import zlib


def audit(image, output, max_compressed, max_expanded):
    if output.exists() or output.is_symlink():
        raise ValueError('new output directory required')
    if image.is_symlink() or not image.is_file():
        raise ValueError('regular non-symlink image required')
    if not 0 < image.stat().st_size <= max_compressed:
        raise ValueError('compressed image size outside limit')
    output.mkdir(parents=True, mode=0o700)
    report = {'passed': False, 'scope': 'untrusted-container-audit-only',
              'publisher_authenticated': False, 'boot_tested': False,
              'device_compatible': None, 'image': image.name}
    try:
        compressed = hashlib.sha256()
        with image.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                compressed.update(block)
        report['observed_compressed_sha256'] = compressed.hexdigest()
        report['compressed_bytes'] = image.stat().st_size
        expanded = hashlib.sha256()
        size = 0
        header = bytearray()
        with gzip.open(image, 'rb') as stream:
            while True:
                block = stream.read(min(1024 * 1024, max_expanded - size + 1))
                if not block:
                    break
                size += len(block)
                if size > max_expanded:
                    raise ValueError('expanded image exceeds limit')
                expanded.update(block)
                if len(header) < 4096:
                    header.extend(block[:4096 - len(header)])
        report.update(expanded_bytes=size, observed_expanded_sha256=expanded.hexdigest(),
                      gzip_crc_checked=True)
        if len(header) >= 28 and header[:4] == b'\x3a\xff\x26\xed':
            magic, major, minor, file_header, chunk_header, block_size, blocks, chunks, checksum = struct.unpack_from('<I4H4I', header)
            if major != 1 or file_header < 28 or chunk_header < 12 or not block_size or not blocks or not chunks:
                raise ValueError('invalid sparse header')
            if block_size * blocks > max_expanded:
                raise ValueError('sparse logical size exceeds limit')
            report.update(container='android-sparse', logical_bytes=block_size * blocks,
                          limitation='Sparse chunks/filesystem NOT validated; needs separate analysis')
        elif len(header) >= 1082 and header[1080:1082] == b'\x53\xef':
            report.update(container='ext4-header',
                          limitation='Magic only; filesystem/AVB/properties NOT validated')
        else:
            raise ValueError('unsupported image header (not recognized ext4 or Android sparse)')
        report['passed'] = True
    except (OSError, EOFError, ValueError, zlib.error) as error:
        report['error'] = str(error)
    (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--max-compressed-bytes', type=int, default=2 * 1024**3)
    parser.add_argument('--max-expanded-bytes', type=int, default=8 * 1024**3)
    args = parser.parse_args()
    if min(args.max_compressed_bytes, args.max_expanded_bytes) <= 0:
        parser.error('positive size limits required')
    try:
        report = audit(args.image, args.output, args.max_compressed_bytes, args.max_expanded_bytes)
    except (OSError, ValueError) as error:
        parser.exit(1, f'FAIL: {error}\n')
    print(json.dumps(report, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
