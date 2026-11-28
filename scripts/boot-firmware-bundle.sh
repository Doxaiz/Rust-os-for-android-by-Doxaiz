#!/usr/bin/env bash
# Boot ONLY a trusted own-build bundle on an already prepared disposable KVM host.
# No APK installation, set-home-activity, root, flashing or identity rewriting.
set -euo pipefail
if [ "$#" -ne 3 ]; then
    echo "Usage: $0 BUNDLE_DIR TRUSTED_METADATA_SHA256 NEW_REPORT_DIR" >&2
    exit 2
fi
repo="$(cd "$(dirname "$0")/.." && pwd)"
bundle="$(cd "$1" && pwd)"
sha="$2"
output="$3"
[[ "$sha" =~ ^[0-9a-f]{64}$ ]] || { echo 'Invalid expected SHA-256' >&2; exit 2; }
[ ! -e "$output" ] && [ ! -L "$output" ] || { echo 'Output already exists' >&2; exit 1; }
[ -r /dev/kvm ] && [ -w /dev/kvm ] || { echo 'KVM read/write access required' >&2; exit 1; }
command -v adb >/dev/null
mkdir -m 700 "$output"
output="$(cd "$output" && pwd)"
cvd="$output/cvd"
python3 "$repo/scripts/unpack-firmware.py" --bundle "$bundle" \
    --metadata-sha256 "$sha" --output "$cvd" > "$output/unpack.log" 2>&1
# Values originate in the verified build metadata, not getprop.
python3 - "$bundle/bundle.json" > "$output/identity.json" <<'PY'
import json, sys
identity = json.load(open(sys.argv[1]))['expected']
for name in ('version', 'fingerprint'):
    if not isinstance(identity[name], str) or not identity[name].strip():
        raise SystemExit('invalid expected identity')
print(json.dumps(identity))
PY
version="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["version"])' "$output/identity.json")"
fingerprint="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["fingerprint"])' "$output/identity.json")"
serial=127.0.0.1:6520
# A pre-existing TCP listener may not yet appear in adb devices.
python3 - <<'PY'
import socket
with socket.socket() as connection:
    connection.settimeout(2)
    if connection.connect_ex(('127.0.0.1', 6520)) == 0:
        raise SystemExit('Refusing an existing TCP listener on port 6520')
PY
# A pre-existing adb target is not ours; never attach to it or stop its VM.
adb start-server > "$output/adb-start.txt" 2>&1
if timeout 10s adb -s "$serial" get-state >/dev/null 2>&1; then
    echo 'Refusing an already-online target on port 6520' >&2
    exit 1
fi
session=()
if [ "${DOXAIZ_CVD_REFRESH_GROUPS:-0}" = 1 ]; then
    session=(sudo -n -u "$(id -un)")
fi
started=0
cleanup() {
    code=$?
    trap - EXIT
    if [ "$started" = 1 ]; then
        timeout 20s adb -s "$serial" logcat -d -t 500 > "$output/logcat.txt" 2>&1 || true
        for name in launcher.log kernel.log; do
            file="$cvd/cuttlefish/instances/cvd-1/logs/$name"
            if [ -f "$file" ]; then
                tail -n 500 "$file" > "$output/$name" || true
            fi
        done
        if ! timeout 60s "${session[@]}" env HOME="$cvd" "$cvd/bin/stop_cvd" > "$output/stop.log" 2>&1; then
            echo 'Cuttlefish cleanup failed; see stop.log' >&2
            [ "$code" -ne 0 ] || code=1
        fi
        adb disconnect "$serial" >/dev/null 2>&1 || true
    fi
    printf 'exit_code=%s\nscope=own-bundle-boot-baseline-only\n' "$code" > "$output/outcome.txt"
    exit "$code"
}
trap cleanup EXIT
started=1
(
    cd "$cvd"
    timeout 900s "${session[@]}" env HOME="$cvd" PATH="$PATH" "$cvd/bin/launch_cvd" \
        --daemon --cpus=2 --memory_mb=2048 --gpu_mode=guest_swiftshader \
        --report_anonymous_usage_stats=n --run_adb_connector=false
) > "$output/launch.log" 2>&1
deadline=$((SECONDS + 300))
while :; do
    timeout 10s adb connect "$serial" >/dev/null 2>&1 || true
    booted="$(timeout 15s adb -s "$serial" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r\n' || true)"
    [ "$booted" = 1 ] && break
    [ "$SECONDS" -lt "$deadline" ] || { echo 'Android boot timed out' >&2; exit 1; }
    sleep 3
done
python3 "$repo/scripts/check-firmware.py" --serial "$serial" \
    --expected-version "$version" --expected-fingerprint "$fingerprint" \
    --output "$output/firmware-gates"
echo 'PASS: own-bundle identity and boot baseline ONLY; NOT CTS, Redmi compatibility or performance.'
