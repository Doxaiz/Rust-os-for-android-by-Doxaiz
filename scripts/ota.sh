#!/usr/bin/env bash
# DoxaizOS: генерация подписанного OTA-пакета из target-files.
# Запускается ТОЛЬКО внутри дерева AOSP/LineageOS после `mka dist` (docs/OTA.md).
#
# Использование:
#   scripts/ota.sh <target-files-signed.zip> <выходной-ota.zip> [полный-from-zip]
#
# Без третьего аргумента генерируется ПОЛНОЕ (full) обновление. Дельта-обновление:
#   scripts/ota.sh new-target-files.zip out.zip old-target-files.zip
set -euo pipefail

if [ $# -lt 2 ] || [ $# -gt 3 ]; then
    echo "Использование: $0 <target-files-signed.zip> <ota.zip> [old-target-files.zip]" >&2
    exit 2
fi
TARGET_FILES="$1"
OUTPUT="$2"
FROM_ZIP="${3:-}"

[ -f "$TARGET_FILES" ] || { echo "Ошибка: не найден $TARGET_FILES" >&2; exit 1; }
[ -z "$FROM_ZIP" ] || [ -f "$FROM_ZIP" ] || { echo "Ошибка: не найден $FROM_ZIP" >&2; exit 1; }

# Скрипт releasetools живёт внутри дерева сборки.
OTA_TOOL="$(find "${ANDROID_BUILD_TOP:-$PWD}" -path '*releasetools/ota_from_target_files' -type f -perm -u+x 2>/dev/null | head -n 1 || true)"
if [ -z "$OTA_TOOL" ]; then
    OTA_TOOL="$(find "${ANDROID_BUILD_TOP:-$PWD}" -name 'ota_from_target_files' -type f 2>/dev/null | grep -v test | head -n 1 || true)"
fi
[ -n "$OTA_TOOL" ] || {
    echo "Ошибка: ota_from_target_files не найден в дереве сборки." >&2
    echo "Скрипт запускается из корня дерева AOSP/LineageOS (ANDROID_BUILD_TOP или cwd)." >&2
    echo "См. docs/OTA.md, раздел 2." >&2
    exit 1
}
echo "releasetools: $OTA_TOOL"

mkdir -p "$(dirname "$OUTPUT")"

if [ -n "$FROM_ZIP" ]; then
    echo "=== Дельта-обновление: $FROM_ZIP -> $TARGET_FILES ==="
    python3 "$OTA_TOOL" -i "$FROM_ZIP" "$TARGET_FILES" "$OUTPUT"
else
    echo "=== Полное обновление из $TARGET_FILES ==="
    python3 "$OTA_TOOL" "$TARGET_FILES" "$OUTPUT"
fi

echo "=== Готово: $OUTPUT ($(du -h "$OUTPUT" | cut -f1)) ==="
if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$OUTPUT"
fi
unzip -l "$OUTPUT" | head -15 || true
echo "Публикация: docs/OTA.md, разделы 3–4 (sha256 укажите в релизных заметках)."
