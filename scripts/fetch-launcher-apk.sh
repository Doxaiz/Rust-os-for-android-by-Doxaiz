#!/usr/bin/env bash
# DoxaizOS: скачивает последний релизный APK Doxaiz Launcher
# (com.doxaiz.launcher) и кладёт его как prebuilt для образа.
# Пакет цели: com.doxaiz.launcher (applicationId из app/build.gradle лаунчера).
#
#   scripts/fetch-launcher-apk.sh            # в overlay этого репозитория
#   scripts/fetch-launcher-apk.sh /путь/AOSP # прямиком в дерево AOSP
#
# Работает через gh (если есть) либо через api.github.com (публичный API,
# без токена, лимит 60 запросов/час достаточно).
set -euo pipefail

REPO="Doxaiz/Doxaiz-android-launcher-"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST_DIR_REL="overlay/vendor/doxaiz/apps/DoxaizLauncher"
DEST_DIR="${REPO_ROOT}/${DEST_DIR_REL}"
if [ $# -eq 1 ]; then
    DEST_DIR="$1/vendor/doxaiz/apps/DoxaizLauncher"
    mkdir -p "$DEST_DIR"
fi
DEST_APK="${DEST_DIR}/DoxaizLauncher.apk"

echo "Источник : github.com/${REPO} (latest release)"
echo "Назначение: ${DEST_APK}"

if command -v gh >/dev/null 2>&1; then
    echo "Скачиваю через gh release download…"
    tmpdir="$(mktemp -d)"
    gh release download --repo "${REPO}" --pattern '*.apk' --dir "${tmpdir}"
    apk="$(find "${tmpdir}" -name '*.apk' | sort | head -n 1)"
    if [ -z "${apk}" ]; then
        echo "Ошибка: в последнем релизе ${REPO} нет *.apk" >&2
        exit 1
    fi
    cp "${apk}" "${DEST_APK}"
    rm -rf "${tmpdir}"
else
    echo "gh не найден, скачиваю через api.github.com…"
    assets_url="$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest" \
        | python3 -c 'import json,sys
d = json.load(sys.stdin)
for a in d.get("assets", []):
    if a.get("name", "").endswith(".apk"):
        print(a["browser_download_url"]); break
')"
    if [ -z "${assets_url}" ]; then
        echo "Ошибка: в последнем релизе ${REPO} нет *.apk (или превышен лимит API)." >&2
        exit 1
    fi
    echo "APK: ${assets_url}"
    curl -fsSL -o "${DEST_APK}" "${assets_url}"
fi

echo "Скачано: $(du -h "${DEST_APK}" | cut -f1)"
if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "${DEST_APK}"
fi
echo "Готово. APK не коммитьте (он в .gitignore) — он только для сборки образа."
