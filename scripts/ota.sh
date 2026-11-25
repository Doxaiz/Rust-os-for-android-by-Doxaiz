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

# Современные releasetools — собранные python_binary_host, не случайный .py.
# Явный override полезен для otatools, распакованных вне дерева сборки.
if [ -n "${DOXAIZ_OTA_TOOL:-}" ]; then
    OTA_TOOL="$DOXAIZ_OTA_TOOL"
elif [ -n "${ANDROID_HOST_OUT:-}" ]; then
    OTA_TOOL="$ANDROID_HOST_OUT/bin/ota_from_target_files"
else
    OTA_TOOL="${ANDROID_BUILD_TOP:-$PWD}/out/host/linux-x86/bin/ota_from_target_files"
fi
[ -f "$OTA_TOOL" ] && [ -x "$OTA_TOOL" ] || {
    echo "Ошибка: не найден исполняемый host-инструмент: $OTA_TOOL" >&2
    echo "В дереве сборки выполните m otatools или задайте DOXAIZ_OTA_TOOL." >&2
    exit 1
}
echo "releasetools: $OTA_TOOL"

# Нельзя заменить один из исходных target-files (включая symlink-алиасы).
python3 - "$TARGET_FILES" "$OUTPUT" "$FROM_ZIP" <<'PYCHECK'
import pathlib, sys
new, output, old = sys.argv[1:]
output = pathlib.Path(output).resolve()
for source in (new, old):
    if source and pathlib.Path(source).resolve() == output:
        raise SystemExit('Ошибка: выходной OTA совпадает с исходным target-files')
PYCHECK

mkdir -p "$(dirname "$OUTPUT")"
tmpdir="$(mktemp -d "$(dirname "$OUTPUT")/.ota-build.XXXXXX")"
trap 'rm -rf "$tmpdir"' EXIT
staged="$tmpdir/update.zip"
args=()
if [ -n "$FROM_ZIP" ]; then
    args+=(-i "$FROM_ZIP")
fi
# Ключ без расширения (.pk8/.x509.pem). Секреты не выводим в лог.
if [ -n "${DOXAIZ_OTA_KEY:-}" ]; then
    args+=(-k "$DOXAIZ_OTA_KEY")
fi
"$OTA_TOOL" "${args[@]}" "$TARGET_FILES" "$staged"

# Контейнер и метаданные — не проверка подписи или совместимости с телефоном.
python3 - "$staged" <<'PYOTA'
import sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as archive:
    if archive.testzip() is not None:
        raise SystemExit('Ошибка: повреждённый OTA ZIP')
    metadata = archive.read('META-INF/com/android/metadata').decode()
    fields = dict(line.split('=', 1) for line in metadata.splitlines() if '=' in line)
    if not fields.get('post-build') or not fields.get('post-timestamp'):
        raise SystemExit('Ошибка: в OTA нет обязательных метаданных сборки')
PYOTA
mv -f "$staged" "$OUTPUT"
echo "=== Готово: $OUTPUT ==="
sha256sum "$OUTPUT"
echo "Публикация: docs/OTA.md (проверка подписи и установка обязательны отдельно)."
