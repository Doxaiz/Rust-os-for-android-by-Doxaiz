#!/usr/bin/env bash
# REAL own-bundle boot path tested with STOCK AOSP, which MUST be rejected.
# Only after cuttlefish-runner has stopped its reference VM. No DoxaizOS claim.
set -euo pipefail
[ "${GITHUB_ACTIONS:-}" = true ] && [ "${RUNNER_ENVIRONMENT:-}" = github-hosted ] || exit 1
repo="$(cd "$(dirname "$0")/.." && pwd)"
: "${REFERENCE_TARGET:?}" "${REFERENCE_BUILD_ID:?}"
mkdir -p reports
sha="$(python3 - <<'PY'
import hashlib, json, os, pathlib, re, shutil, socket
with socket.socket() as connection:
    connection.settimeout(2)
    if connection.connect_ex(('127.0.0.1', 6520)) == 0:
        raise SystemExit('Reference VM still listening; refusing to remove its directory')
root = pathlib.Path.home() / '.cuttlefish-runner'
target, build = os.environ['REFERENCE_TARGET'], os.environ['REFERENCE_BUILD_ID']
if not re.fullmatch(r'aosp_cf_x86_64_only_phone-userdebug', target) or not re.fullmatch(r'[0-9]+', build):
    raise SystemExit('Unexpected reference build/target')
# The action has already stopped this disposable reference VM. Reclaim its
# unpacked images, not the downloads needed for the new negative-control boot.
shutil.rmtree(root / 'cvd')
bundle = pathlib.Path('reports/stock-negative-bundle')
bundle.mkdir(mode=0o700)
dl = root / 'downloads' / f'{target}-{build}'
for name, source in [('images.zip', dl / f'{target.rsplit("-", 1)[0]}-img-{build}.zip'),
                     ('cvd-host_package.tar.gz', dl / 'cvd-host_package.tar.gz')]:
    os.link(source, bundle / name)
# Deliberately SYNTHETIC metadata for a rejection control; NOT an exported
# DoxaizOS build and NOT an actual pinned AOSP source manifest.
(bundle / 'repo-manifest.xml').write_text('<manifest><project name="SYNTHETIC-NEGATIVE-CONTROL-NOT-AOSP-PROVENANCE" revision="' + '0' * 40 + '"/></manifest>')
def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()
metadata = {'schema': 1, 'scope': 'STOCK-NEGATIVE-CONTROL-NOT-DOXAIZOS',
            'source_commit': '0' * 40,
            'expected': {'version': 'negative-control-must-not-match-stock',
                         'fingerprint': 'negative-control-not-a-build-fingerprint', 'low_ram': True},
            'artifacts': {}}
for name in ('images.zip', 'cvd-host_package.tar.gz', 'repo-manifest.xml'):
    path = bundle / name
    metadata['artifacts'][name] = {'sha256': digest(path), 'bytes': path.stat().st_size}
(bundle / 'bundle.json').write_text(json.dumps(metadata, indent=2))
print(digest(bundle / 'bundle.json'))
PY
)"
set +e
DOXAIZ_CVD_REFRESH_GROUPS=1 bash "$repo/scripts/boot-firmware-bundle.sh" \
    reports/stock-negative-bundle "$sha" reports/stock-own-path-negative
status=$?
set -e
[ "$status" -ne 0 ] || { echo 'ERROR: stock image unexpectedly passed own-firmware gates' >&2; exit 1; }
python3 - <<'PY'
import json, pathlib
root = pathlib.Path('reports/stock-own-path-negative')
result = json.loads((root / 'firmware-gates/result.json').read_text())
assert result['passed'] is False
assert result['error'] == 'DoxaizOS version matches independent expected build', result
assert (root / 'stop.log').exists(), 'cleanup was not attempted'
message = 'PASS NEGATIVE CONTROL: real stock image booted via own-bundle path and correctly rejected. NOT DoxaizOS.'
(root / 'negative-control.txt').write_text(message + '\n')
print(message)
PY
