#!/usr/bin/env bash
# Collect existing diagnostics, without root, flashing, reset, or force-stop.
# Usage: bash scripts/collect-device.sh SERIAL NEW_OUTPUT_DIRECTORY
set -euo pipefail

if [ "$#" -ne 2 ] || [ -z "$1" ] || [ -z "$2" ]; then
    echo "Использование: $0 ADB_SERIAL НОВЫЙ_КАТАЛОГ_ОТЧЁТА" >&2
    exit 2
fi
serial="$1"
output="$2"
command -v adb >/dev/null 2>&1 || { echo "Не найден adb." >&2; exit 1; }
command -v timeout >/dev/null 2>&1 || { echo "Нужен GNU timeout (coreutils)." >&2; exit 1; }
if [ -e "$output" ] || [ -L "$output" ]; then
    echo "Каталог отчёта уже существует; перезапись запрещена: $output" >&2
    exit 1
fi

# Every call uses the explicitly selected serial, never the default device.
adb_cmd() { timeout 30s adb -s "$serial" "$@"; }
state="$(adb_cmd get-state | tr -d '\r\n')"
[ "$state" = device ] || { echo "Устройство не готово: $state" >&2; exit 1; }
boot="$(adb_cmd shell getprop sys.boot_completed | tr -d '\r\n')"
[ "$boot" = 1 ] || { echo "Android ещё не загрузился." >&2; exit 1; }
adb_cmd shell pm path com.doxaiz.launcher | grep -q '^package:' || {
    echo "Пакет com.doxaiz.launcher не найден." >&2
    exit 1
}

mkdir -p -- "$(dirname -- "$output")"
staging="$(mktemp -d "$(dirname -- "$output")/.device-report.XXXXXX")"
trap 'rm -rf -- "$staging"' EXIT
# Some diagnostics can contain app names / build fingerprints: private by default.
chmod 700 "$staging"
adb_cmd shell cat /proc/meminfo > "$staging/meminfo.txt"
adb_cmd shell dumpsys meminfo com.doxaiz.launcher > "$staging/pss.txt"
adb_cmd shell dumpsys gfxinfo com.doxaiz.launcher > "$staging/gfxinfo.txt"
for name in meminfo pss gfxinfo; do
    [ -s "$staging/$name.txt" ] || { echo "Пустой вывод $name; отчёт не опубликован." >&2; exit 1; }
done
{
    printf 'collected_at_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'package=com.doxaiz.launcher\n'
    for prop in ro.build.fingerprint ro.build.version.sdk ro.config.low_ram ro.doxaiz.version; do
        printf '%s=' "$prop"
        adb_cmd shell getprop "$prop" | tr -d '\r'
    done
    printf 'note=Existing cumulative gfxinfo; no reset or cold-start measurement performed.\n'
} > "$staging/context.txt"
# GNU mv -n avoids overwriting a destination created concurrently; verify move.
mv -T -n -- "$staging" "$output"
if [ -d "$staging" ]; then
    echo "Назначение появилось во время сбора; отчёт не опубликован." >&2
    exit 1
fi
printf 'Сохранено: %s\nЭто исходные данные, не подтверждение бюджета или готовности ОС.\n' "$output"
