#!/usr/bin/env bash
# DoxaizOS: копирует вендорский overlay в дерево исходников AOSP/LineageOS
# как vendor/doxaiz. Идемпотентен.
#
# Использование:
#   scripts/apply-overlay.sh /путь/к/дереву-AOSP
set -euo pipefail

if [ $# -ne 1 ]; then
    echo "Использование: $0 /путь/к/дереву-AOSP" >&2
    exit 2
fi
AOSP_DIR="$1"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="${REPO_ROOT}/overlay/vendor/doxaiz"
DST="${AOSP_DIR}/vendor/doxaiz"

# Дерево AOSP/LineageOS обязательно содержит этот файл (после repo init).
if [ ! -f "${AOSP_DIR}/build/envsetup.sh" ] && [ ! -f "${AOSP_DIR}/build/make/envsetup.sh" ]; then
    echo "Ошибка: ${AOSP_DIR} не похож на дерево AOSP (нет build/envsetup.sh)." >&2
    echo "См. docs/BUILD.md, шаг 3: repo init -u https://github.com/LineageOS/android.git -b lineage-24.0" >&2
    exit 1
fi

echo "Каталог AOSP : ${AOSP_DIR}"
echo "Overlay      : ${SRC} -> ${DST}"

mkdir -p "${DST}"
# Копируем содержимое overlay (products/, apps/, etc/, Android.mk).
cp -a "${SRC}/." "${DST}/"

echo "Готово. Теперь:"
echo "  1) устройство (per-device): добавьте в product make-файл строку:"
echo "       \$(call inherit-product, vendor/doxaiz/products/doxaiz_base.mk)"
echo "     (для cuttlefish найдите его с помощью: grep -r 'PRODUCT_NAME' device/google/cuttlefish/*.mk)"
echo "  2) любой Treble-телефон (GSI): lunch покажет doxaiz_arm64-userdebug"
echo "     (через vendor/doxaiz/AndroidProducts.mk; см. docs/GSI.md)"
echo "  3) scripts/fetch-launcher-apk.sh"
echo "  4) lunch <target> && m -j\$(nproc)"
echo "Полностью: docs/BUILD.md (per-device) и docs/GSI.md (на любой телефон)."
