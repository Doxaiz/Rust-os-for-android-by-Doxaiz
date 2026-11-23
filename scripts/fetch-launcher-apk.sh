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
if [ $# -gt 1 ]; then
    echo "Использование: $0 [путь/AOSP]" >&2
    exit 2
fi
if [ $# -eq 1 ]; then
    DEST_DIR="$1/vendor/doxaiz/apps/DoxaizLauncher"
    mkdir -p "$DEST_DIR"
fi
mkdir -p "$DEST_DIR"
DEST_APK="${DEST_DIR}/DoxaizLauncher.apk"
# Временный каталог на той же ФС: проверенный APK публикуется атомарным mv.
tmpdir="$(mktemp -d "${DEST_DIR}/.launcher-download.XXXXXX")"
trap 'rm -rf "$tmpdir"' EXIT
STAGED_APK="${tmpdir}/DoxaizLauncher.apk"

echo "Источник : github.com/${REPO} (latest release)"
echo "Назначение: ${DEST_APK}"

# Имя последнего тега — нужно для проверки apk-sha256.txt. Узнаём один раз.
TAG_NAME="$(curl -fsSL --max-time 30 "https://api.github.com/repos/${REPO}/releases/latest" | python3 -c 'import json,sys
try:
    print(json.load(sys.stdin).get("tag_name",""))
except Exception:
    print("")' || true)"
if [ -z "$TAG_NAME" ]; then
    echo "Ошибка: не удалось определить тег релиза; существующий APK не изменён." >&2
    exit 1
fi
echo "Последний релиз: ${TAG_NAME}"

if command -v gh >/dev/null 2>&1; then
    echo "Скачиваю через gh release download…"
    gh release download "$TAG_NAME" --repo "${REPO}" --pattern '*.apk' --dir "${tmpdir}"
    apk="$(find "${tmpdir}" -name '*.apk' | sort | head -n 1)"
    if [ -z "${apk}" ]; then
        echo "Ошибка: в последнем релизе ${REPO} нет *.apk" >&2
        exit 1
    fi
    mv "${apk}" "${STAGED_APK}"
else
    echo "gh не найден, скачиваю через api.github.com…"
    assets_url="$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/tags/${TAG_NAME}" \
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
    curl -fsSL --max-time 120 -o "${STAGED_APK}" "${assets_url}"
fi

# --- Проверка целостности (sha256) -------------------------------------------
# Релизы лаунчера публикуют apk-sha256.txt рядом с APK. Если его удалось
# скачать и разобрать — проверяем обязательно: несовпадение = hard fail
# (битый/подменённый APK). Если скачать не удалось (офлайн-зеркало, нет сети,
# файл отсутствует) — только предупреждение: на релизных сборках проверьте
# вручную https://github.com/<repo>/releases/latest
if [ -z "${TAG_NAME}" ]; then
    echo "ПРЕДУПРЕЖДЕНИЕ: тег последнего релиза неизвестен — проверка sha256 пропущена." >&2
else
    SHA_URL="https://github.com/${REPO}/releases/download/${TAG_NAME}/apk-sha256.txt"
    echo "Проверяю sha256 (${SHA_URL})…"
    actual="$(sha256sum "${STAGED_APK}" | awk '{print $1}')"
    echo "Фактический sha256: ${actual}"
    if curl -fsSL --max-time 30 -o "${tmpdir}/apk-sha256.txt" "${SHA_URL}" 2>/dev/null; then
        expected="$(grep -oE '[0-9a-fA-F]{64}' "${tmpdir}/apk-sha256.txt" | head -n 1 | tr 'A-F' 'a-f' || true)"
        rm -f "${tmpdir}/apk-sha256.txt"
        if [ -z "${expected}" ]; then
            echo "ПРЕДУПРЕЖДЕНИЕ: apk-sha256.txt скачан, но sha256 в нём не распознан — проверка пропущена." >&2
        elif [ "${expected}" != "${actual}" ]; then
            echo "ОШИБКА: sha256 APK НЕ совпал с apk-sha256.txt из релиза!" >&2
            echo "  ожидалось: ${expected}" >&2
            echo "  получено : ${actual}" >&2
            echo "APK мог быть повреждён при скачивании или подменён. Не используйте." >&2
            exit 1
        else
            echo "sha256 OK — APK совпадает с релизным apk-sha256.txt"
        fi
    else
        echo "ПРЕДУПРЕЖДЕНИЕ: apk-sha256.txt недоступен — целостность НЕ проверена" >&2
        echo "  (APK скачан с того же release; но на релизных сборках сверьте хеш вручную)" >&2
    fi
fi

# Минимальная проверка контейнера; это не проверка подписи/идентичности пакета.
python3 - "$STAGED_APK" <<'PYAPK'
import sys, zipfile
with zipfile.ZipFile(sys.argv[1]) as apk:
    names = apk.namelist()
    if 'AndroidManifest.xml' not in names or 'classes.dex' not in names:
        raise SystemExit('Ошибка: файл не является ожидаемым APK')
    if apk.testzip() is not None:
        raise SystemExit('Ошибка: повреждённый ZIP/APK')
PYAPK
mv -f "$STAGED_APK" "$DEST_APK"
echo "Готово. APK не коммитьте (он в .gitignore) — он только для сборки образа."
