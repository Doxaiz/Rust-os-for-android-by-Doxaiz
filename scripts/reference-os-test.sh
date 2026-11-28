#!/usr/bin/env bash
# Reference AOSP firmware infrastructure test, NOT a DoxaizOS acceptance PASS.
# Only for the disposable local Cuttlefish created by the pinned CI action.
set -euo pipefail
serial="${ANDROID_SERIAL:?Cuttlefish action must set ANDROID_SERIAL}"
case "$serial" in
    127.0.0.1:6520|localhost:6520) ;;
    *) echo "Refusing unexpected target: $serial" >&2; exit 1 ;;
esac
adb_cmd() { timeout 20s adb -s "$serial" "$@"; }
hardware="$(adb_cmd shell getprop ro.hardware | tr -d '\r\n')"
case "$hardware" in
    cutf_*|cuttlefish*) ;;
    *) echo "Refusing non-Cuttlefish hardware: $hardware" >&2; exit 1 ;;
esac
report="reports/cuttlefish-reference"
[ ! -e "$report" ] || { echo "Report already exists" >&2; exit 1; }
mkdir -p "$report"
trap 'adb_cmd logcat -d -t 300 > "$report/logcat.txt" 2>&1 || true' EXIT
[ "$(adb_cmd shell getprop sys.boot_completed | tr -d '\r\n')" = 1 ]
[ "$(adb_cmd shell getenforce | tr -d '\r\n')" = Enforcing ]
adb_cmd shell getprop > "$report/properties-before.txt"
adb_cmd shell service list > "$report/services-before.txt"
for name in activity package window; do
    grep -E "[[:space:]]${name}:" "$report/services-before.txt" >/dev/null
done
before="$(adb_cmd shell settings get global boot_count | tr -d '\r\n')"
[[ "$before" =~ ^[0-9]+$ ]]
marker="doxaiz-lab-${GITHUB_RUN_ID:-manual}"
adb_cmd shell "printf '%s' '$marker' > /data/local/tmp/doxaiz-lab-persistence"
adb_cmd shell sync
adb_cmd reboot
deadline=$((SECONDS + 300))
ready=0
while [ "$SECONDS" -lt "$deadline" ]; do
    timeout 10s adb connect "$serial" >/dev/null 2>&1 || true
    booted="$(adb_cmd shell getprop sys.boot_completed 2>/dev/null | tr -d '\r\n' || true)"
    after="$(adb_cmd shell settings get global boot_count 2>/dev/null | tr -d '\r\n' || true)"
    if [ "$booted" = 1 ] && [[ "$after" =~ ^[0-9]+$ ]] && [ "$after" -gt "$before" ]; then
        ready=1
        break
    fi
    sleep 3
done
[ "$ready" = 1 ] || { echo "No confirmed Android reboot" >&2; exit 1; }
[ "$(adb_cmd shell cat /data/local/tmp/doxaiz-lab-persistence | tr -d '\r\n')" = "$marker" ]
[ "$(adb_cmd shell getenforce | tr -d '\r\n')" = Enforcing ]
adb_cmd shell service list > "$report/services-after.txt"
for name in activity package window; do
    grep -E "[[:space:]]${name}:" "$report/services-after.txt" >/dev/null
done
adb_cmd shell cat /proc/meminfo > "$report/meminfo.txt"
adb_cmd shell df -k /data > "$report/storage.txt"
printf 'PASS: reference AOSP boot, SELinux, core services, reboot and userdata persistence.\nNOT DoxaizOS, NOT Redmi 9A compatibility, NOT a performance-budget result.\nboot_count_before=%s\nboot_count_after=%s\n' "$before" "$after" | tee "$report/result.txt"
