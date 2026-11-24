"""Offline integration tests: real downloader, fake network commands, temporary tree.

Run: python3 -m unittest discover -s scripts/tests -v
No GitHub access, Android SDK, or third-party Python packages required.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile


SCRIPT = Path(__file__).resolve().parents[1] / "fetch-launcher-apk.sh"
TAG = "v-test-pinned"
MOCK = r'''
import json, os, pathlib, shutil, sys
args = sys.argv[1:]
mode = os.environ['CASE']
with open(os.environ['CALLS'], 'a') as log:
    log.write(json.dumps([pathlib.Path(sys.argv[0]).name] + args) + '\n')
if pathlib.Path(sys.argv[0]).name == 'gh':
    assert args[:3] == ['release', 'download', 'v-test-pinned'], args
    if mode == 'download_failure':
        sys.exit(22)
    if mode != 'no_asset':
        shutil.copyfile(os.environ['FIXTURE'], pathlib.Path(args[args.index('--dir')+1])/'release.apk')
else:
    url = args[-1]
    if url.endswith('/releases/latest'):
        print('{}' if mode == 'no_tag' else '{"tag_name":"v-test-pinned"}')
    elif '/releases/tags/' in url:
        assert url.endswith('/v-test-pinned'), url
        print(json.dumps({'assets': [] if mode == 'no_asset' else [
            {'name': 'release.apk', 'browser_download_url': 'https://github.com/mock/release.apk'}]}))
    elif url.endswith('apk-sha256.txt'):
        assert '/v-test-pinned/' in url, url
        if mode == 'checksum_missing':
            sys.exit(22)
        value = os.environ['HASH']
        if mode == 'mismatch':
            value = '0' * 64
        if mode == 'checksum_invalid':
            value = 'not-a-checksum'
        pathlib.Path(args[args.index('-o')+1]).write_text(value + '  release.apk\n')
    elif url == 'https://github.com/mock/release.apk':
        if mode == 'download_failure':
            sys.exit(22)
        shutil.copyfile(os.environ['FIXTURE'], args[args.index('-o')+1])
    else:
        raise AssertionError(url)
'''


class FetchLauncherTests(unittest.TestCase):
    def run_case(self, mode, with_gh):
        with tempfile.TemporaryDirectory(prefix="launcher test ") as tmp:
            root = Path(tmp)
            bin_dir = root / 'bin'
            bin_dir.mkdir()
            # Deliberately isolated PATH, so host gh/network tools cannot leak in.
            for cmd in ('bash', 'dirname', 'mkdir', 'mktemp', 'rm', 'find',
                        'sort', 'head', 'mv', 'sha256sum', 'awk', 'grep', 'tr'):
                executable = shutil.which(cmd)
                self.assertIsNotNone(executable, cmd)
                (bin_dir / cmd).symlink_to(executable)
            (bin_dir / 'python3').symlink_to(sys.executable)
            for cmd in (('curl', 'gh') if with_gh else ('curl',)):
                mock = bin_dir / cmd
                mock.write_text('#!' + sys.executable + '\n' + MOCK)
                mock.chmod(0o755)
            fixture = root / 'fixture.apk'
            if mode == 'bad_zip':
                fixture.write_bytes(b'not an apk')
            else:
                with zipfile.ZipFile(fixture, 'w') as apk:
                    apk.writestr('AndroidManifest.xml', b'test manifest')
                    if mode != 'missing_dex':
                        apk.writestr('classes.dex', b'test dex')
            if mode == 'bad_crc':
                # ZIP_STORED payload changes without updating its CRC in the directory.
                fixture.write_bytes(fixture.read_bytes().replace(b'test dex', b'BAD! dex'))
            tree = root / 'android tree'
            dest = tree / 'vendor/doxaiz/apps/DoxaizLauncher/DoxaizLauncher.apk'
            dest.parent.mkdir(parents=True)
            dest.write_bytes(b'existing prebuilt')
            calls = root / 'calls.jsonl'
            env = dict(os.environ, PATH=str(bin_dir), CASE=mode,
                       FIXTURE=str(fixture), CALLS=str(calls),
                       HASH=hashlib.sha256(fixture.read_bytes()).hexdigest())
            result = subprocess.run([str(bin_dir / 'bash'), str(SCRIPT), str(tree)],
                                    env=env, text=True, capture_output=True, timeout=15)
            success = mode in ('valid', 'checksum_missing', 'checksum_invalid')
            output = result.stdout + result.stderr
            self.assertEqual(result.returncode == 0, success, output)
            self.assertEqual(dest.read_bytes(), fixture.read_bytes() if success
                             else b'existing prebuilt', output)
            self.assertEqual(list(dest.parent.glob('.launcher-download.*')), [], output)
            if mode.startswith('checksum_'):
                self.assertIn('ПРЕДУПРЕЖДЕНИЕ', output)
                self.assertNotIn('sha256 OK', output)
            if mode == 'valid':
                self.assertIn('sha256 OK', output)
            requests = [json.loads(line) for line in calls.read_text().splitlines()]
            self.assertEqual(sum('/releases/latest' in r[-1] for r in requests), 1)

    def test_download_paths_and_failure_safety(self):
        for with_gh in (True, False):
            for mode in ('valid', 'mismatch', 'no_tag', 'download_failure',
                         'no_asset', 'bad_zip', 'bad_crc', 'missing_dex',
                         'checksum_missing', 'checksum_invalid'):
                with self.subTest(with_gh=with_gh, mode=mode):
                    self.run_case(mode, with_gh)


if __name__ == '__main__':
    unittest.main()
