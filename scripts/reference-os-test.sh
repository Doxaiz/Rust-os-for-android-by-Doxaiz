#!/usr/bin/env bash
# Reference AOSP firmware infrastructure test, NOT DoxaizOS acceptance.
set -euo pipefail
repo="$(cd "$(dirname "$0")/.." && pwd)"
report=reports/cuttlefish-reference
python3 "$repo/scripts/check-os-lifecycle.py" \
    --serial "${ANDROID_SERIAL:?Cuttlefish action must set ANDROID_SERIAL}" \
    --output "$report" --allow-disposable-reboot
python3 - "$report" <<'PY'
import json
from pathlib import Path
import sys
root = Path(sys.argv[1])
result = json.loads((root / 'result.json').read_text())
assert result['passed'] is True
message = ('PASS: reference AOSP kernel reboot, SELinux, services and userdata persistence.\n'
           'NOT DoxaizOS, NOT Redmi 9A compatibility, NOT a performance-budget result.\n'
           f'boot_count_before={result["boot_count_before"]}\n'
           f'boot_count_after={result["boot_count_after"]}\n')
(root / 'result.txt').write_text(message)
print(message, end='')
PY
