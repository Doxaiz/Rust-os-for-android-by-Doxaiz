"""Fixture tests for SOURCE changes only; not an Android build or role test."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = '''<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="com.android.launcher3">
    <application>
        <activity android:name=".Launcher"
            android:taskAffinity=""
            android:exported="true"
            android:enabled="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <action android:name="android.intent.action.SHOW_WORK_APPS" />
                <action android:name="android.intent.action.ALL_APPS" />
                <category android:name="android.intent.category.HOME" />
                <category android:name="android.intent.category.DEFAULT" />
            </intent-filter>
        </activity>
        <service android:name=".QuickstepService" android:exported="true" />
    </application>
</manifest>
'''


class HomeSourcePatchTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('git'), 'git needed')
    def test_apply_idempotence_missing_and_drift(self):
        for case in ('good', 'missing', 'drift'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                tree = Path(tmp)
                launcher = tree / 'packages/apps/Launcher3'
                (launcher / 'quickstep').mkdir(parents=True)
                for name in ('AndroidManifest.xml', 'quickstep/AndroidManifest-launcher.xml'):
                    (launcher / name).write_text(MANIFEST)
                if case == 'missing':
                    (launcher / 'AndroidManifest.xml').unlink()
                if case == 'drift':
                    (launcher / 'quickstep/AndroidManifest-launcher.xml').write_text(
                        MANIFEST.replace('android:enabled="true"', 'android:enabled="false"'))
                before = {str(p): p.read_bytes() for p in launcher.rglob('*.xml')}
                command = ['bash', str(ROOT / 'scripts/apply-home-fallback-patch.sh'), str(tree)]
                result = subprocess.run(command, capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode == 0, case == 'good', result.stdout + result.stderr)
                after = {str(p): p.read_bytes() for p in launcher.rglob('*.xml')}
                if case == 'good':
                    for content in after.values():
                        self.assertIn(b'android:priority="-1"', content)
                        self.assertIn(b'QuickstepService', content)
                    repeat = subprocess.run(command, capture_output=True, text=True, timeout=10)
                    self.assertEqual(repeat.returncode, 0, repeat.stderr)
                    self.assertEqual(after, {str(p): p.read_bytes() for p in launcher.rglob('*.xml')})
                else:
                    self.assertEqual(before, after)


if __name__ == '__main__':
    unittest.main()
