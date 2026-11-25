#!/usr/bin/env bash
# DoxaizOS: запустить собранный Cuttlefish-образ и установить на него
# Doxaiz Launcher. См. docs/BUILD.md, раздел «Проверка на Cuttlefish».
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APK="${1:-${REPO_ROOT}/overlay/vendor/doxaiz/apps/DoxaizLauncher/DoxaizLauncher.apk}"
ADB_TARGET="${DOXAIZ_ADB_TARGET:-127.0.0.1:6520}"

command -v launch_cvd >/dev/null 2>&1 || {
    echo "Не найден launch_cvd. Установите Cuttlefish:" >&2
    echo "  git clone https://github.com/google/android-cuttlefish && cd android-cuttlefish && \
./tools/buildutils/build_packages.sh" >&2
    echo "  sudo dpkg -i cuttlefish-base_*.deb cuttlefish-user_*.deb  # + usermod -aG kvm \$USER; reboot" >&2
    exit 1
}

command -v adb >/dev/null 2>&1 || {
    echo "Не найден adb (Android platform-tools)." >&2
    exit 1
}
BOOT_TIMEOUT="${DOXAIZ_BOOT_TIMEOUT:-300}"
if ! [[ "$BOOT_TIMEOUT" =~ ^[0-9]+$ ]] || [ "${#BOOT_TIMEOUT}" -gt 5 ]; then
    echo "DOXAIZ_BOOT_TIMEOUT должен быть целым числом секунд (0–99999)." >&2
    exit 2
fi
BOOT_TIMEOUT=$((10#$BOOT_TIMEOUT))

echo "=== Запускаю Cuttlefish (--daemon) ==="
launch_cvd --daemon

echo "=== Жду загрузку Android (${ADB_TARGET}, ${BOOT_TIMEOUT} с) ==="
deadline=$((SECONDS + BOOT_TIMEOUT))
while :; do
    # Повторное подключение нужно, если adbd ещё не слушал при первом connect.
    adb connect "${ADB_TARGET}" >/dev/null 2>&1 || true
    booted="$(adb -s "${ADB_TARGET}" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r\n' || true)"
    if [ "$booted" = "1" ]; then
        echo "Android загрузился: ${ADB_TARGET}"
        break
    fi
    if [ "$SECONDS" -ge "$deadline" ]; then
        echo "Ошибка: Android не загрузился за ${BOOT_TIMEOUT} с (${ADB_TARGET})." >&2
        adb devices -l >&2 || true
        exit 1
    fi
    sleep 2
done

if [ -f "${APK}" ]; then
    echo "=== Устанавливаю ${APK} ==="
    adb -s "${ADB_TARGET}" install -r "${APK}"
else
    echo "APK не найден: ${APK} (пропускаю установку — запустите scripts/fetch-launcher-apk.sh)"
fi

# APK может быть уже встроен в образ; отсутствие локального файла допустимо
# только если целевой пакет действительно установлен.
if ! adb -s "${ADB_TARGET}" shell pm path com.doxaiz.launcher | grep -q '^package:'; then
    echo "Ошибка: com.doxaiz.launcher не установлен; назначение HOME невозможно." >&2
    exit 1
fi

echo "=== Назначаю Doxaiz Launcher главным экраном ==="
adb -s "${ADB_TARGET}" shell cmd package set-home-activity com.doxaiz.launcher/.MainActivity
home="$(adb -s "${ADB_TARGET}" shell cmd package resolve-activity --brief \
    -a android.intent.action.MAIN -c android.intent.category.HOME | tr -d '\r')"
if ! grep -q '^com\.doxaiz\.launcher/' <<< "$home"; then
    echo "Ошибка: HOME не разрешается в Doxaiz Launcher: $home" >&2
    exit 1
fi

echo "=== Диагностика памяти (целевой бюджет — docs/ARCHITECTURE.md) ==="
adb -s "${ADB_TARGET}" shell cat /proc/meminfo | grep -E 'MemTotal|MemFree|MemAvailable'
adb -s "${ADB_TARGET}" shell dumpsys meminfo | sed -n '1,30p'
echo "=== Готово. Веб-интерфейс: https://localhost:8443 ==="
