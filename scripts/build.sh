#!/usr/bin/env bash
# DoxaizOS: полная сборка прошивки. ВНИМАНИЕ: требует мощный ПК
# (официальный ориентир AOSP: 64 ГБ ОЗУ, 400 ГБ свободно, Linux x86_64) — в CI такой прогон не делаем,
# см. docs/BUILD.md «Где собирать».
#
# Использование:
#   scripts/build.sh /путь/к/будущему/дереву LUNCH_TARGET
# Примеры:
#   scripts/build.sh ~/android/doxaiz doxaiz_cf_x86_64_phone-trunk_staging-userdebug # Cuttlefish (ещё не собран)
#   scripts/build.sh ~/android/doxaiz lineage_<device>-userdebug                   # реальное устройство
#   scripts/build.sh ~/android/doxaiz doxaiz_arm64-userdebug                       # GSI (только совместимые ARM64; docs/GSI.md)
set -euo pipefail

if [ $# -ne 2 ]; then
    echo "Использование: $0 /путь/к/будущему/дереву LUNCH_TARGET" >&2
    exit 2
fi
# Абсолютный путь нужен до cd: иначе helper-скрипты получат вложенный путь.
mkdir -p "$1"
TREE="$(cd "$1" && pwd -P)"
LUNCH_TARGET="$2"
LINEAGE_BRANCH="${DOXAIZ_LINEAGE_BRANCH:-lineage-24.0}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== DoxaizOS: сборка прошивки ==="
echo "Дерево   : ${TREE}"
echo "Ветка LOS: ${LINEAGE_BRANCH}"
echo "Lunch    : ${LUNCH_TARGET}"

mem_gb=$(awk '/MemTotal/ {printf "%d", $2/1024/1024}' /proc/meminfo)
disk_gb=$(df -BG --output=avail "${TREE}" 2>/dev/null | tail -1 | tr -dc '0-9' || echo 0)
echo "Ресурсы  : RAM ~${mem_gb} ГБ, свободно на диске ~${disk_gb} ГБ"
if [ "${mem_gb:-0}" -lt 64 ]; then
    echo "Предупреждение: меньше официального ориентира AOSP 64 ГБ ОЗУ; успешная сборка не гарантируется." >&2
fi
if [ "${disk_gb:-0}" -lt 400 ]; then
    echo "Предупреждение: меньше официального ориентира AOSP 400 ГБ свободного диска." >&2
fi

command -v repo >/dev/null 2>&1 || {
    echo "Не найден инструмент repo. docs/BUILD.md, шаг 2:" >&2
    echo "  mkdir -p ~/bin && curl -o ~/bin/repo https://storage.googleapis.com/git-repo-downloads/repo && chmod +x ~/bin/repo" >&2
    exit 1
}

mkdir -p "${TREE}"
cd "${TREE}"

if [ ! -d .repo ]; then
    echo "=== repo init (${LINEAGE_BRANCH}) ==="
    repo init -u https://github.com/LineageOS/android.git -b "${LINEAGE_BRANCH}" --depth=1
fi
echo "=== Локальный манифест DoxaizOS ==="
mkdir -p .repo/local_manifests
cp "${REPO_ROOT}/manifest/doxaiz.xml" .repo/local_manifests/doxaiz.xml
echo "=== repo sync (может занять часы; local manifest уже установлен) ==="
repo sync -c --no-tags --optimized-fetch --prune -j"$(nproc)"

echo "=== Overlay DoxaizOS ==="
"${REPO_ROOT}/scripts/apply-overlay.sh" "${TREE}"

case "$LUNCH_TARGET" in
    doxaiz_cf_x86_64_phone-*)
        echo "=== Начальный HOME: Launcher3 остаётся запасным (-1), Doxaiz APK не меняется ==="
        bash "${REPO_ROOT}/scripts/apply-home-fallback-patch.sh" "$TREE"
        ;;
esac

echo "=== Prebuilt APK лаунчера ==="
DOXAIZ_ALLOW_UNVERIFIED_APK=0 "${REPO_ROOT}/scripts/fetch-launcher-apk.sh" "${TREE}"

echo "=== НЕ ЗАБУДЬТЕ (вручную, один раз) ==="
echo "добавить строку в product make-файл вашего устройства:"
echo "  \$(call inherit-product, vendor/doxaiz/products/doxaiz_base.mk)"
echo "  (см. docs/BUILD.md, шаг 6 — без неё DoxaizOS в образ не попадёт)"
echo

echo "=== envsetup + lunch + m ==="
# shellcheck disable=SC1091
. build/envsetup.sh
lunch "${LUNCH_TARGET}"

echo "=== Проверяю выбранный продукт DoxaizOS ==="
# Запрашиваем вычисленные Make-переменные, а не grep по исходникам:
# наличие overlay на диске ещё не означает, что продукт его наследует.
packages="$(build/soong/soong_ui.bash --dumpvar-mode PRODUCT_PACKAGES)"
properties="$(build/soong/soong_ui.bash --dumpvar-mode PRODUCT_PROPERTY_OVERRIDES)"
python3 - "$packages" "$properties" <<'PYPRODUCT'
import sys
packages = sys.argv[1].split()
properties = sys.argv[2].split()
if 'DoxaizLauncher' not in packages:
    raise SystemExit('Ошибка: выбранный продукт не включает DoxaizLauncher; подключите doxaiz_base.mk')
if 'ro.config.low_ram=true' not in properties or not any(
        value.startswith('ro.doxaiz.version=') and value.split('=', 1)[1]
        for value in properties):
    raise SystemExit('Ошибка: в продукте нет low-RAM свойств/версии DoxaizOS; проверьте наследование doxaiz_base.mk')
PYPRODUCT
m -j"$(nproc)"

echo "=== Готово. Артефакты: ${TREE}/out/target/product/ ==="
