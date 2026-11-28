#!/usr/bin/env bash
# Integration experiment ONLY on disposable stock Cuttlefish userdebug.
# Pushes our existing APK + XML into overlayfs, creates a fresh user, checks
# initial HOME and user choice persistence. NOT a built DoxaizOS firmware test.
set -euo pipefail
[ "${GITHUB_ACTIONS:-}" = true ] && [ "${RUNNER_ENVIRONMENT:-}" = github-hosted ] || {
    echo 'Refusing system mutation outside a disposable hosted runner' >&2; exit 1;
}
serial="${ANDROID_SERIAL:?}"
[ "$serial" = 127.0.0.1:6520 ] || { echo 'Unexpected serial' >&2; exit 1; }
repo="$(cd "$(dirname "$0")/.." && pwd)"
report="$repo/reports/home-policy"
[ ! -e "$report" ] || { echo 'Report already exists' >&2; exit 1; }
mkdir -p "$report"
adb_cmd() { timeout 30s adb -s "$serial" "$@"; }
prop() { adb_cmd shell getprop "$1" | tr -d '\r\n'; }
case "$(prop ro.hardware)" in cutf_*|cuttlefish*) ;; *) exit 1 ;; esac
case "$(prop ro.build.type)" in userdebug|eng) ;; *) exit 1 ;; esac
[ "$(prop sys.boot_completed)" = 1 ]
user_id=''
cleanup() {
    code=$?
    trap - EXIT
    adb_cmd logcat -d -t 500 > "$report/logcat.txt" 2>&1 || true
    if [ -n "$user_id" ]; then
        timeout 90s adb -s "$serial" shell am switch-user -w 0 > "$report/return-user.txt" 2>&1 || true
        adb_cmd shell am stop-user -w -f "$user_id" > "$report/stop-user.txt" 2>&1 || true
        adb_cmd shell pm remove-user "$user_id" > "$report/remove-user.txt" 2>&1 || true
    fi
    if [ "$code" -ne 0 ]; then
        echo '::error::HOME policy integration failed; see home-policy report. NOT a DoxaizOS boot result.'
    fi
    exit "$code"
}
trap cleanup EXIT
# Reconnect after adbd restarts without trusting wait-for-device indefinitely.
wait_boot() {
    deadline=$((SECONDS + 240))
    while [ "$SECONDS" -lt "$deadline" ]; do
        timeout 10s adb connect "$serial" >/dev/null 2>&1 || true
        [ "$(prop sys.boot_completed 2>/dev/null || true)" = 1 ] && return 0
        sleep 3
    done
    echo 'Android did not boot within deadline' >&2
    return 1
}
root_adb() {
    adb_cmd root
    deadline=$((SECONDS + 60))
    while [ "$SECONDS" -lt "$deadline" ]; do
        timeout 10s adb connect "$serial" >/dev/null 2>&1 || true
        [ "$(adb_cmd shell id -u 2>/dev/null | tr -d '\r\n' || true)" = 0 ] && return 0
        sleep 2
    done
    return 1
}
reboot_guest() {
    before="$(adb_cmd shell settings get global boot_count | tr -d '\r\n')"
    [[ "$before" =~ ^[0-9]+$ ]]
    adb_cmd reboot
    deadline=$((SECONDS + 240))
    while [ "$SECONDS" -lt "$deadline" ]; do
        timeout 10s adb connect "$serial" >/dev/null 2>&1 || true
        after="$(adb_cmd shell settings get global boot_count 2>/dev/null | tr -d '\r\n' || true)"
        if [[ "$after" =~ ^[0-9]+$ ]] && [ "$after" -gt "$before" ] && [ "$(prop sys.boot_completed 2>/dev/null || true)" = 1 ]; then
            return 0
        fi
        sleep 3
    done
    return 1
}
stock_home="$(adb_cmd shell cmd package resolve-activity --brief \
    -a android.intent.action.MAIN -c android.intent.category.HOME | tr -d '\r' | tail -n 1)"
[[ "$stock_home" =~ ^com\.android\.launcher3/ ]] || { echo "Unexpected stock HOME: $stock_home" >&2; exit 1; }
printf '%s\n' "$stock_home" > "$report/stock-home.txt"
bash "$repo/scripts/fetch-launcher-apk.sh" > "$report/apk-download.txt" 2>&1
root_adb > "$report/root-before.txt" 2>&1
adb_cmd disable-verity > "$report/disable-verity.txt" 2>&1
reboot_guest
root_adb > "$report/root-remount.txt" 2>&1
adb_cmd remount > "$report/remount-first.txt" 2>&1
# Overlayfs may require an extra reboot on modern dynamic partitions.
reboot_guest
root_adb > "$report/root-push.txt" 2>&1
adb_cmd remount > "$report/remount-second.txt" 2>&1
adb_cmd shell mkdir -p /system/app/DoxaizLauncher /system/etc/preferred-apps
adb_cmd push "$repo/overlay/vendor/doxaiz/apps/DoxaizLauncher/DoxaizLauncher.apk" /system/app/DoxaizLauncher/DoxaizLauncher.apk
adb_cmd push "$repo/overlay/vendor/doxaiz/etc/preferred-apps/doxaiz-home.xml" /system/etc/preferred-apps/doxaiz-home.xml
adb_cmd shell chmod 644 /system/app/DoxaizLauncher/DoxaizLauncher.apk /system/etc/preferred-apps/doxaiz-home.xml
adb_cmd shell restorecon -RF /system/app/DoxaizLauncher /system/etc/preferred-apps
adb_cmd shell sync
reboot_guest
adb_cmd shell pm path com.doxaiz.launcher > "$report/package-path.txt"
grep -q '^package:/system/app/DoxaizLauncher/' "$report/package-path.txt"
adb_cmd shell pm create-user DoxaizHomePolicyTest > "$report/create-user.txt"
user_id="$(sed -n 's/.*created user id \([0-9][0-9]*\).*/\1/p' "$report/create-user.txt" | tr -d '\r')"
[[ "$user_id" =~ ^[0-9]+$ ]] && [ "$user_id" -gt 0 ]
adb_cmd shell am start-user -w "$user_id" > "$report/start-user.txt"
# A fresh background user still resolves to Provision by design. Exercise
# normal foreground provisioning; never disable SetupWizard or write its
# completion settings to force the policy test to pass.
timeout 90s adb -s "$serial" shell am switch-user -w "$user_id" > "$report/switch-user.txt"
adb_cmd shell wm dismiss-keyguard > "$report/unlock-user.txt"
adb_cmd shell am start --user "$user_id" -W -a android.intent.action.MAIN \
    -c android.intent.category.HOME > "$report/start-home.txt"
deadline=$((SECONDS + 90))
while :; do
    complete="$(adb_cmd shell settings --user "$user_id" get secure user_setup_complete | tr -d '\r\n')"
    [ "$complete" = 1 ] && break
    [ "$SECONDS" -lt "$deadline" ] || { echo 'New user provisioning did not complete' >&2; exit 1; }
    sleep 3
done
resolve_home() {
    adb_cmd shell cmd package resolve-activity --user "$user_id" --brief \
        -a android.intent.action.MAIN -c android.intent.category.HOME | tr -d '\r' | tail -n 1
}
home="$(resolve_home)"
printf '%s\n' "$home" > "$report/initial-home.txt"
[ "$home" = com.doxaiz.launcher/.MainActivity ] || [ "$home" = com.doxaiz.launcher/com.doxaiz.launcher.MainActivity ]
# TEST-ONLY simulation of an explicit user choice. This is not used by the
# own-firmware acceptance path, which never assigns HOME.
adb_cmd shell cmd package set-home-activity --user "$user_id" "$stock_home" > "$report/user-choice.txt"
[ "$(resolve_home)" = "$stock_home" ]
reboot_guest
adb_cmd shell am start-user -w "$user_id" > "$report/start-user-after-reboot.txt"
[ "$(resolve_home)" = "$stock_home" ]
[ "$(adb_cmd shell getenforce | tr -d '\r\n')" = Enforcing ]
printf '%s\n' 'PASS: initial HOME XML and explicit user choice across reboot on modified STOCK AOSP.' \
    'NOT a DoxaizOS image build/boot. Overlayfs+system APK injection was used for this integration experiment.' \
    > "$report/result.txt"
cat "$report/result.txt"
