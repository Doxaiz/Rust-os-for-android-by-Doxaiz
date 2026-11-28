"""Test actual workflow shell wiring with fake cargo, not a Rust/image test."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[2]


class HardeningWorkflowTests(unittest.TestCase):
    def test_actual_shell_passes_exact_three_extracted_config_paths(self):
        workflow = (ROOT / '.github/workflows/ready-base.yml').read_text()
        step = workflow.split('      - name: Prepare Rust two-file patch', 1)[1]
        script = step.split('        run: |\n', 1)[1].split("          python3 - <<'PY'", 1)[0]
        script = textwrap.dedent(script)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = root / 'cargo'
            binary.write_text('#!' + sys.executable + '\n' + '''import json, os, sys
with open(os.environ['CARGO_CALLS'], 'a') as stream:
    stream.write(json.dumps(sys.argv[1:]) + '\\n')
''')
            binary.chmod(0o755)
            calls = root / 'calls.jsonl'
            env = dict(os.environ, PATH=str(root) + ':' + os.environ['PATH'], CARGO_CALLS=str(calls))
            result = subprocess.run(['bash', '-eu', '-c', script], env=env, cwd=root,
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            recorded = [json.loads(line) for line in calls.read_text().splitlines()]
            self.assertEqual(recorded[0], ['--version'])
            self.assertEqual(len(recorded), 2)
            self.assertEqual(recorded[1], ['run', '--release', '--manifest-path', 'core/Cargo.toml',
                '-p', 'doxaiz-hardening', '--bin', 'doxaiz-harden-remote', '--',
                'reports/ready-base/inspection/system-etc-init-phh-remotectl.rc.txt',
                'reports/ready-base/inspection/system-bin-phh-remotectl.sh.txt',
                'reports/ready-base/remote-patch'])


if __name__ == '__main__':
    unittest.main()
