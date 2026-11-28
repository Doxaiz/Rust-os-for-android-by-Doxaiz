#!/usr/bin/env bash
# Build-time SOURCE patch for doxaiz_cf_x86_64_phone only, never an ADB command.
# Retains Launcher3/Quickstep for fallback/recents; leaves Doxaiz APK untouched.
set -euo pipefail
[ "$#" = 1 ] || { echo "Usage: $0 ANDROID_TREE" >&2; exit 2; }
repo="$(cd "$(dirname "$0")/.." && pwd)"
tree="$(cd "$1" && pwd)"
launcher="$tree/packages/apps/Launcher3"
patch="$repo/patches/lineage-24.0/launcher3-home-fallback.patch"
[ -f "$launcher/AndroidManifest.xml" ] && [ -f "$launcher/quickstep/AndroidManifest-launcher.xml" ] || {
    echo 'Launcher3 source manifests missing; refusing to skip initial-HOME integration' >&2; exit 1;
}
if git -C "$launcher" apply --check "$patch" 2>/dev/null; then
    git -C "$launcher" apply "$patch"
elif git -C "$launcher" apply --reverse --check "$patch" 2>/dev/null; then
    echo 'HOME fallback patch already applied'
else
    echo 'Launcher3 manifests changed: neither exact forward nor reverse patch applies; review upstream' >&2
    exit 1
fi
python3 - "$launcher" <<'PY'
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
root = Path(sys.argv[1])
android = '{http://schemas.android.com/apk/res/android}'
for name in ('AndroidManifest.xml', 'quickstep/AndroidManifest-launcher.xml'):
    manifest = ET.parse(root / name).getroot()
    homes = [f for f in manifest.iter('intent-filter')
             if any(c.get(android + 'name') == 'android.intent.category.HOME'
                    for c in f.findall('category'))]
    if len(homes) != 1 or homes[0].get(android + 'priority') != '-1':
        raise SystemExit(f'Unexpected HOME filter in {name}')
print('SOURCE PATCH ONLY: stock HOME priority -1; requires real build/boot/recents/fallback testing')
PY
