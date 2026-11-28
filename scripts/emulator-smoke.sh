#!/usr/bin/env bash
# Functional launcher smoke test on an expendable Android Emulator ONLY.
# Does not build/test the DoxaizOS system image or emulate Redmi hardware.
set -euo pipefail
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 LAUNCHER_APK NEW_REPORT_DIRECTORY" >&2
    exit 2
fi
apk="$1"
output="$2"
serial="${DOXAIZ_ADB_TARGET:-emulator-5554}"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ -f "$apk" ] || { echo "APK missing: $apk" >&2; exit 1; }
case "$serial" in
    emulator-[0-9]*) ;;
    *) echo "Refusing non-emulator serial: $serial" >&2; exit 1 ;;
esac
adb_cmd() { timeout 45s adb -s "$serial" "$@"; }
[ "$(adb_cmd shell getprop ro.kernel.qemu | tr -d '\r\n')" = 1 ] || {
    echo "Refusing device without ro.kernel.qemu=1" >&2
    exit 1
}
[ ! -e "$output" ] && [ ! -L "$output" ] || { echo "Report already exists" >&2; exit 1; }
mkdir -p "$output"
# Preserve evidence even when an assertion fails. Only emulator data is collected.
evidence() {
    adb_cmd logcat -d -t 500 > "$output/logcat.txt" 2>&1 || true
    adb_cmd exec-out screencap -p > "$output/screen.png" 2>/dev/null || true
}
trap evidence EXIT
adb_cmd shell getprop > "$output/emulator-properties.txt"
sha256sum "$apk" > "$output/apk-sha256.txt"
adb_cmd install -r "$apk"
adb_cmd shell cmd package set-home-activity com.doxaiz.launcher/.MainActivity
adb_cmd shell am start -W -n com.doxaiz.launcher/.MainActivity > "$output/start.txt"
grep -q '^Status: ok' "$output/start.txt"
adb_cmd shell cmd package resolve-activity --brief \
    -a android.intent.action.MAIN -c android.intent.category.HOME > "$output/home.txt"
grep -q '^com\.doxaiz\.launcher/' "$output/home.txt"
adb_cmd shell input keyevent KEYCODE_HOME
resumed=0
for _ in {1..15}; do
    adb_cmd shell dumpsys activity activities > "$output/activities.txt"
    if grep -E '(mResumedActivity|topResumedActivity).*com\.doxaiz\.launcher/' "$output/activities.txt" >/dev/null; then
        resumed=1
        break
    fi
    sleep 1
done
[ "$resumed" = 1 ] || { echo "Launcher is not resumed" >&2; exit 1; }
adb_cmd shell pidof com.doxaiz.launcher > "$output/pid.txt"
[ -s "$output/pid.txt" ]
bash "$root/scripts/collect-device.sh" "$serial" "$output/diagnostics"
printf 'PASS: released launcher installed and resumed as HOME on stock Android Emulator.\nNot a DoxaizOS firmware, memory-budget, A64, or Redmi 9A compatibility test.\n' | tee "$output/result.txt"
