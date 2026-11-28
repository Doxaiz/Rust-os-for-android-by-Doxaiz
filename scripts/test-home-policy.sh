#!/usr/bin/env bash
# NEGATIVE integration experiment ONLY on disposable stock Cuttlefish userdebug.
# Pushes our existing APK + XML into overlayfs, creates a fresh user, checks
# XML-alone failure and user choice persistence. NOT a built DoxaizOS firmware test.
set -Eeuo pipefail
[ "${GITHUB_ACTIONS:-}" = true ] && [ "${RUNNER_ENVIRONMENT:-}" = github-hosted ] || {
    echo 'Refusing system mutation outside a disposable hosted runner' >&2; exit 1;
}
serial="${ANDROID_SERIAL:?}"
[ "$serial" = 127.0.0.1:6520 ] || { echo 'Unexpected serial' >&2; exit 1; }
repo="$(cd "$(dirname "$0")/.." && pwd)"
report="$repo/reports/home-policy"
[ ! -e "$report" ] || { echo 'Report already exists' >&2; exit 1; }
mkdir -p "$report"
trap 'printf "line=%s command=%s\n" "$LINENO" "$BASH_COMMAND" > "$report/failure.txt"' ERR
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
    # adbd can close its transport while switching UID and return nonzero;
    # success is determined by id -u, never by hiding a failed root request.
    adb_cmd root || true
    deadline=$((SECONDS + 60))
    while [ "$SECONDS" -lt "$deadline" ]; do
        timeout 10s adb connect "$serial" >/dev/null 2>&1 || true
        [ "$(adb_cmd shell id -u 2>/dev/null | tr -d '\r\n' || true)" = 0 ] && return 0
        adb_cmd root || true
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
adb_cmd shell dumpsys package preferred > "$report/preferred-before-provision.txt"
adb_cmd shell cat /system/etc/preferred-apps/doxaiz-home.xml > "$report/policy-on-device.txt"
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
# Provision and RoleController complete asynchronously. Observe without
# assigning a holder; a chooser still present after the deadline is failure.
home_deadline=$((SECONDS + 45))
while :; do
    home="$(resolve_home)"
    case "$home" in com.doxaiz.launcher/.MainActivity|com.doxaiz.launcher/com.doxaiz.launcher.MainActivity) break ;; esac
    [ "$SECONDS" -lt "$home_deadline" ] || break
    sleep 2
done
adb_cmd shell dumpsys package preferred > "$report/preferred-after-provision.txt"
adb_cmd shell cmd package query-activities --user "$user_id" --brief \
    -a android.intent.action.MAIN -c android.intent.category.HOME > "$report/home-candidates.txt"
adb_cmd shell cmd role get-role-holders --user "$user_id" android.app.role.HOME > "$report/home-role.txt"
printf '%s\n' "$home" > "$report/initial-home.txt"
# The earlier positive hypothesis FAILED on the real platform. Preserve it
# as a precise negative regression, not a green "default HOME works" claim.
[ "$home" = android/com.android.internal.app.ResolverActivity ]
python3 - "$report" <<'PYCONTROL'
from pathlib import Path
import sys
root = Path(sys.argv[1])
candidates = (root / 'home-candidates.txt').read_text()
assert 'com.doxaiz.launcher/.MainActivity' in candidates
assert 'com.android.launcher3/' in candidates
assert candidates.count('priority=0 ') == 2, candidates
assert not (root / 'home-role.txt').read_text().strip(), 'Unexpected HOME holder'
PYCONTROL
# Isolate explicit-choice persistence from the disproven XML policy. Do not
# silently leave a boot-time default input installed during a different test.
# This changes the experiment, NOT the production image or acceptance gates.
root_adb > "$report/root-remove-xml.txt" 2>&1
adb_cmd remount > "$report/remount-remove-xml.txt" 2>&1
adb_cmd shell rm /system/etc/preferred-apps/doxaiz-home.xml
adb_cmd shell test ! -e /system/etc/preferred-apps/doxaiz-home.xml
adb_cmd shell sync
printf '%s\n' 'XML-alone negative control finished; XML removed before explicit choices.' \
    > "$report/choice-test-scope.txt"
# TEST-ONLY simulation of an explicit user choice. This is not used by the
# own-firmware acceptance path, which never assigns HOME.
adb_cmd shell cmd package set-home-activity --user "$user_id" com.doxaiz.launcher/.MainActivity > "$report/user-choice-doxaiz.txt"
[ "$(resolve_home)" = com.doxaiz.launcher/.MainActivity ]
# A secondary user is not necessarily foreground/unlocked after a device
# reboot. Recreate the same user context as before reboot, without assigning
# HOME again. Keep observations before/after foregrounding to diagnose races.
verify_choice_after_reboot() {
    local phase="$1" expected="$2" observed choice_deadline
    # PMS schedules preferred-activity restrictions writes with a 10 s delay
    # (lineage-24.0). Test SETTLED persistence, not immediate power-loss safety.
    # sync alone cannot flush a write still queued in system_server memory.
    adb_cmd shell dumpsys package preferred > "$report/$phase-before-settle-preferred.txt"
    sleep 20
    adb_cmd shell dumpsys package preferred > "$report/$phase-after-settle-preferred.txt"
    adb_cmd shell sync
    reboot_guest
    adb_cmd shell test ! -e /system/etc/preferred-apps/doxaiz-home.xml
    resolve_home > "$report/$phase-background-home.txt"
    adb_cmd shell cmd role get-role-holders --user "$user_id" android.app.role.HOME \
        > "$report/$phase-background-role.txt"
    adb_cmd shell am start-user -w "$user_id" > "$report/$phase-start-user.txt"
    timeout 90s adb -s "$serial" shell am switch-user -w "$user_id" > "$report/$phase-switch-user.txt"
    adb_cmd shell wm dismiss-keyguard > "$report/$phase-unlock.txt"
    choice_deadline=$((SECONDS + 45))
    while :; do
        observed="$(resolve_home)"
        printf '%s\n' "$observed" >> "$report/$phase-resolve-history.txt"
        [ "$observed" = "$expected" ] && break
        [ "$SECONDS" -lt "$choice_deadline" ] || break
        sleep 2
    done
    adb_cmd shell cmd role get-role-holders --user "$user_id" android.app.role.HOME \
        > "$report/$phase-foreground-role.txt"
    adb_cmd shell dumpsys package preferred > "$report/$phase-preferred.txt"
    [ "$observed" = "$expected" ]
}
verify_choice_after_reboot doxaiz-choice com.doxaiz.launcher/.MainActivity
adb_cmd shell cmd package set-home-activity --user "$user_id" "$stock_home" > "$report/user-choice.txt"
[ "$(resolve_home)" = "$stock_home" ]
verify_choice_after_reboot stock-choice "$stock_home"
[ "$(adb_cmd shell getenforce | tr -d '\r\n')" = Enforcing ]
printf '%s\n' 'PASS NEGATIVE CONTROL: XML alone leaves a chooser; AFTER XML REMOVAL AND 20s SETTLE explicit choices of Doxaiz and stock HOME each survive reboot.' \
    'NOT a DoxaizOS image build/boot. Overlayfs+system APK injection was used for this integration experiment.' \
    > "$report/result.txt"
cat "$report/result.txt"
