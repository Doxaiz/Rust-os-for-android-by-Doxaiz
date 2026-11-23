#!/usr/bin/env bash
# DoxaizOS: полная сборка прошивки. ВНИМАНИЕ: требует мощный ПК
# (≥ 16 ГБ ОЗУ, ≥ 250 ГБ SSD, Linux x86_64) — в CI такой прогон не делаем,
# см. docs/BUILD.md «Где собирать».
#
# Использование:
#   scripts/build.sh /путь/к/будущему/дереву LUNCH_TARGET
# Примеры:
#   scripts/build.sh ~/android/doxaiz aosp_cf_x86_64_phone-trunk_staging-userdebug   # Cuttlefish
#   scripts/build.sh ~/android/doxaiz lineage_<device>-userdebug                   # реальное устройство
set -euo pipefail

if [ $# -ne 2 ]; then
    echo "Использование: $0 /путь/к/будущему/дереву LUNCH_TARGET" >&2
    exit 2
fi
TREE="$1"
LUNCH_TARGET="$2"
LINEAGE_BRANCH="${DOXAIZ_LINEAGE_BRANCH:-lineage-24.0}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== DoxaizOS: сборка прошивки ==="
echo "Дерево   : ${TREE}"
echo "Ветка LOS: ${LINEAGE_BRANCH}"
echo "Lunch    : ${LUNCH_TARGET}"

mem_gb=$(awk '/MemTotal/ {printf "%d", $2/1024/1024}' /proc/meminfo)
disk_gb=$(df -BG --output=avail "${TREE%/*}" 2>/dev/null | tail -1 | tr -dc '0-9' || echo 0)
echo "Ресурсы  : RAM ~${mem_gb} ГБ, свободно на диске ~${disk_gb} ГБ"
if [ "${mem_gb:-0}" -lt 12 ]; then
    echo "Предупреждение: меньше 12 ГБ ОЗУ — сборка AOSP, скорее всего, не пройдёт." >&2
fi
if [ "${disk_gb:-0}" -lt 200 ]; then
    echo "Предупреждение: меньше 200 ГБ на диске — полная синхронизация AOSP не влезет." >&2
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
echo "=== repo sync (может занять часы) ==="
repo sync -c --no-tags --optimized-fetch --prune -j"$(nproc)"

echo "=== Локальный манифест DoxaizOS ==="
mkdir -p .repo/local_manifests
cp "${REPO_ROOT}/manifest/doxaiz.xml" .repo/local_manifests/doxaiz.xml
repo sync -c --no-tags --optimized-fetch --prune -j"$(nproc)"

echo "=== Overlay DoxaizOS ==="
"${REPO_ROOT}/scripts/apply-overlay.sh" "${TREE}"

echo "=== Prebuilt APK лаунчера ==="
"${REPO_ROOT}/scripts/fetch-launcher-apk.sh" "${TREE}"

echo "=== НЕ ЗАБУДЬТЕ (вручную, один раз) ==="
echo "добавить строку в product make-файл вашего устройства:"
echo "  \$(call inherit-product, vendor/doxaiz/products/doxaiz_base.mk)"
echo "  (см. docs/BUILD.md, шаг 6 — без неё DoxaizOS в образ не попадёт)"
echo

echo "=== envsetup + lunch + m ==="
# shellcheck disable=SC1091
. build/envsetup.sh
lunch "${LUNCH_TARGET}"
m -j"$(nproc)"

echo "=== Готово. Артефакты: ${TREE}/out/target/product/ ==="
