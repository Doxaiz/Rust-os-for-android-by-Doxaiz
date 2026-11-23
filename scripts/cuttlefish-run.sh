#!/usr/bin/env bash
# DoxaizOS: запустить собранный Cuttlefish-образ и установить на него
# Doxaiz Launcher. См. docs/BUILD.md, раздел «Проверка на Cuttlefish».
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APK="${1:-${REPO_ROOT}/overlay/vendor/doxaiz/apps/DoxaizLauncher/DoxaizLauncher.apk}"
ADB_TARGET="${DOXAIZ_ADB_TARGET:-0.0.0.0:6520}"

command -v launch_cvd >/dev/null 2>&1 || {
    echo "Не найден launch_cvd. Установите Cuttlefish:" >&2
    echo "  git clone https://github.com/google/android-cuttlefish && cd android-cuttlefish && \
./tools/buildutils/build_packages.sh" >&2
    echo "  sudo dpkg -i cuttlefish-base_*.deb cuttlefish-user_*.deb  # + usermod -aG kvm \$USER; reboot" >&2
    exit 1
}

echo "=== Запускаю Cuttlefish (--daemon) ==="
launch_cvd --daemon

echo "=== Жду adb (${ADB_TARGET}) ==="
adb connect "${ADB_TARGET}" >/dev/null || true
for i in $(seq 1 60); do
    if adb -s "${ADB_TARGET}" get-state >/dev/null 2>&1; then
        echo "Устройство в сети: ${ADB_TARGET}"
        break
    fi
    sleep 2
    if [ "$i" -eq 60 ]; then
        echo "Ошибка: устройство не появилось за 2 минуты" >&2
        exit 1
    fi
done

if [ -f "${APK}" ]; then
    echo "=== Устанавливаю ${APK} ==="
    adb -s "${ADB_TARGET}" install -r "${APK}"
else
    echo "APK не найден: ${APK} (пропускаю установку — запустите scripts/fetch-launcher-apk.sh)"
fi

echo "=== Назначаю Doxaiz Launcher главным экраном ==="
adb -s "${ADB_TARGET}" shell cmd package set-home-activity com.doxaiz.launcher/.MainActivity || \
    adb -s "${ADB_TARGET}" shell am start -a android.intent.action.MAIN -c android.intent.category.HOME

echo "=== Диагностика памяти (целевой бюджет — docs/ARCHITECTURE.md) ==="
adb -s "${ADB_TARGET}" shell cat /proc/meminfo | grep -E 'MemTotal|MemFree|MemAvailable'
adb -s "${ADB_TARGET}" shell dumpsys meminfo | head -30
echo "=== Готово. Веб-интерфейс: https://localhost:8443 ==="
