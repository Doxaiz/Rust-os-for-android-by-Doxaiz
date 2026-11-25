"""OTA wrapper regression tests with a fake executable host tool, no Android build."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'ota.sh'
TOOL = r'''
import json, os, pathlib, sys, zipfile
pathlib.Path(os.environ['CALLS']).write_text(json.dumps(sys.argv[1:]))
out = pathlib.Path(sys.argv[-1])
if os.environ['CASE'] == 'tool_failure':
    out.write_bytes(b'partial output')
    sys.exit(1)
if os.environ['CASE'] == 'bad_zip':
    out.write_bytes(b'bad zip')
else:
    with zipfile.ZipFile(out, 'w') as z:
        if os.environ['CASE'] != 'missing_metadata':
            z.writestr('META-INF/com/android/metadata',
                       'post-build=doxaiz/test\npost-timestamp=123456\n')
'''


class OtaTests(unittest.TestCase):
    def test_generation_and_safety(self):
        for mode in ('full', 'incremental', 'tool_failure', 'bad_zip',
                     'missing_metadata', 'missing_tool', 'same_input', 'symlink_input'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(prefix='ota test ') as tmp:
                root = Path(tmp)
                new, old, output = (root / n for n in ('new.zip', 'old.zip', 'output.zip'))
                new.write_bytes(b'new target files')
                old.write_bytes(b'old target files')
                output.write_bytes(b'previous OTA')
                tool = root / 'ota_from_target_files'
                tool.write_text('#!' + sys.executable + '\n' + TOOL)
                tool.chmod(0o755)
                calls = root / 'calls.json'
                env = dict(os.environ, DOXAIZ_OTA_TOOL=str(tool), CASE=mode,
                           CALLS=str(calls), DOXAIZ_OTA_KEY=str(root / 'keys/releasekey'))
                if mode == 'missing_tool':
                    tool.unlink()
                if mode == 'same_input':
                    output = new
                if mode == 'symlink_input':
                    output.unlink()
                    output.symlink_to(new)
                before = output.read_bytes()
                args = ['bash', str(SCRIPT), str(new), str(output)]
                if mode == 'incremental':
                    args.append(str(old))
                result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=10)
                success = mode in ('full', 'incremental')
                self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
                self.assertEqual(list(root.glob('.ota-build.*')), [])
                if success:
                    command = json.loads(calls.read_text())
                    self.assertIn('-k', command)
                    self.assertEqual(command[command.index('-k') + 1], env['DOXAIZ_OTA_KEY'])
                    if mode == 'incremental':
                        self.assertEqual(command[:2], ['-i', str(old)])
                    else:
                        self.assertNotIn('-i', command)
                    self.assertNotEqual(output.read_bytes(), before)
                else:
                    self.assertEqual(output.read_bytes(), before)
                    if mode in ('missing_tool', 'same_input', 'symlink_input'):
                        self.assertFalse(calls.exists())
                self.assertEqual(new.read_bytes(), b'new target files')
                self.assertEqual(old.read_bytes(), b'old target files')


if __name__ == '__main__':
    unittest.main()
