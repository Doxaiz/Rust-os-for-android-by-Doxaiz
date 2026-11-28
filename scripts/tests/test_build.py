"""Build orchestration with fake repo/envsetup/network, never downloads Android."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from test_fetch_launcher import MOCK
from test_home_source_patch import MANIFEST

SCRIPT = Path(__file__).resolve().parents[1] / 'build.sh'
REPO = r"""
import os, pathlib, sys
root = pathlib.Path.cwd()
with open(os.environ['BUILD_CALLS'], 'a') as f:
    f.write(sys.argv[1] + '\n')
if sys.argv[1] == 'init':
    (root / '.repo').mkdir()
elif sys.argv[1] == 'manifest':
    if os.environ['BUILD_CASE'] == 'manifest_failure': sys.exit(1)
    revision = 'main' if os.environ['BUILD_CASE'] == 'unpinned_manifest' else 'a' * 40
    pathlib.Path(sys.argv[sys.argv.index('-o') + 1]).write_text(
        '<manifest><project name="fixture" revision="' + revision + '"/></manifest>')
elif sys.argv[1] == 'diff':
    if os.environ['BUILD_CASE'] == 'diff_failure': sys.exit(1)
    print('fixture source diff')
elif sys.argv[1] == 'sync':
    assert (root / '.repo/local_manifests/doxaiz.xml').is_file()
    if os.environ['BUILD_CASE'] == 'sync_failure':
        sys.exit(1)
    (root / 'build/soong').mkdir(parents=True, exist_ok=True)
    soong = root / 'build/soong/soong_ui.bash'
    soong.write_text('''
#!/bin/bash
[ "$BUILD_CASE" != dumpvar_failure ] || exit 1
case "$2" in
  PRODUCT_PACKAGES)
    if [ "$BUILD_CASE" = missing_launcher ]; then
      echo DoxaizLauncherFake
    else
      printf 'Settings\\nDoxaizLauncher SystemUI\\n'
    fi ;;
  PRODUCT_PROPERTY_OVERRIDES)
    if [ "$BUILD_CASE" = missing_properties ]; then
      echo ro.config.low_ram=false
    else
      echo ro.config.low_ram=true ro.doxaiz.version=0.1.0
    fi ;;
  *) exit 2 ;;
esac
'''.lstrip())
    soong.chmod(0o755)
    (root / 'build/envsetup.sh').write_text('''
function lunch() {
    echo "lunch $*" >> "$BUILD_CALLS"
    [ "$BUILD_CASE" != lunch_failure ]
}
function m() {
    echo "m $*" >> "$BUILD_CALLS"
    [ "$BUILD_CASE" != build_failure ]
}
''')
else:
    raise AssertionError(sys.argv)
"""


class BuildTests(unittest.TestCase):
    def test_orchestration(self):
        for mode in ('relative', 'absolute', 'existing_tree', 'sync_failure',
                     'lunch_failure', 'build_failure', 'missing_launcher',
                     'missing_properties', 'dumpvar_failure', 'unverified_apk',
                     'cf_source_missing', 'cf_source_ok', 'manifest_failure', 'unpinned_manifest', 'diff_failure'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(prefix='build test ') as tmp:
                root = Path(tmp)
                bindir = root / 'bin'
                bindir.mkdir()
                for cmd, code in (('repo', REPO), ('curl', MOCK), ('gh', MOCK)):
                    executable = bindir / cmd
                    executable.write_text('#!' + sys.executable + '\n' + code)
                    executable.chmod(0o755)
                fixture = root / 'fixture.apk'
                with zipfile.ZipFile(fixture, 'w') as apk:
                    apk.writestr('AndroidManifest.xml', 'mock')
                    apk.writestr('classes.dex', 'mock')
                tree = root / 'android tree'
                if mode == 'existing_tree':
                    (tree / '.repo').mkdir(parents=True)
                if mode == 'cf_source_ok':
                    launcher = tree / 'packages/apps/Launcher3'
                    (launcher / 'quickstep').mkdir(parents=True)
                    for name in ('AndroidManifest.xml', 'quickstep/AndroidManifest-launcher.xml'):
                        (launcher / name).write_text(MANIFEST)
                build_calls = root / 'build-calls'
                env = dict(os.environ, PATH=str(bindir) + ':' + os.environ['PATH'],
                           CASE='checksum_missing' if mode == 'unverified_apk' else 'valid',
                           DOXAIZ_ALLOW_UNVERIFIED_APK='1',
                           BUILD_CASE=mode, BUILD_CALLS=str(build_calls),
                           CALLS=str(root / 'network-calls'), FIXTURE=str(fixture),
                           HASH=hashlib.sha256(fixture.read_bytes()).hexdigest())
                target = str(tree) if mode == 'absolute' else 'android tree'
                lunch = 'doxaiz_cf_x86_64_phone-trunk_staging-userdebug' if mode.startswith('cf_source_') else 'test-userdebug'
                result = subprocess.run(['bash', str(SCRIPT), target, lunch],
                                        cwd=root, env=env, capture_output=True, text=True, timeout=20)
                success = mode in ('relative', 'absolute', 'existing_tree', 'cf_source_ok')
                self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
                trace = build_calls.read_text().splitlines()
                self.assertEqual(trace.count('sync'), 1)
                self.assertEqual(trace.count('init'), 0 if mode == 'existing_tree' else 1)
                if success:
                    self.assertIn('lunch ' + lunch, trace)
                    if mode == 'cf_source_ok':
                        self.assertIn('android:priority="-1"',
                                      (tree / 'packages/apps/Launcher3/AndroidManifest.xml').read_text())
                    self.assertTrue(any(line.startswith('m -j') for line in trace))
                    self.assertIn('=== Готово.', result.stdout)
                    evidence = next(tree.glob('doxaiz-build-evidence.*'))
                    metadata = json.loads((evidence / 'source-evidence.json').read_text())
                    self.assertEqual(metadata['lunch_target'], lunch)
                    self.assertEqual(metadata['sha256']['DoxaizLauncher.apk'], env['HASH'])
                    self.assertEqual(hashlib.sha256((evidence / 'source-diff.patch').read_bytes()).hexdigest(),
                                     metadata['sha256']['source-diff.patch'])
                    self.assertEqual(json.loads((evidence / 'result.json').read_text())['build_exit_code'], 0)

                    self.assertTrue((tree / 'vendor/doxaiz/products/doxaiz_base.mk').is_file())
                    self.assertEqual((tree / 'vendor/doxaiz/apps/DoxaizLauncher/DoxaizLauncher.apk').read_bytes(),
                                     fixture.read_bytes())
                    self.assertFalse((tree / 'android tree').exists())
                else:
                    self.assertNotIn('=== Готово.', result.stdout)
                    evidence_dirs = list(tree.glob('doxaiz-build-evidence.*'))
                    if evidence_dirs:
                        status = json.loads((evidence_dirs[0] / 'result.json').read_text())
                        self.assertNotEqual(status['build_exit_code'], 0)
                        self.assertIn(status['last_phase'], ('source-evidence', 'lunch', 'product-gates', 'compile'))

                if mode in ('sync_failure', 'lunch_failure', 'missing_launcher',
                            'missing_properties', 'dumpvar_failure', 'unverified_apk', 'cf_source_missing',
                            'manifest_failure', 'unpinned_manifest', 'diff_failure'):
                    self.assertFalse(any(line.startswith('m ') for line in trace))


if __name__ == '__main__':
    unittest.main()
