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

# Manifest -r alone omits our local Launcher3 patch. Capture both only after
# overlay/patch/APK preparation; fail before compilation if evidence is missing.
# This directory is outside out/ so a later Android clean does not remove it.
EVIDENCE="$(mktemp -d "${TREE}/doxaiz-build-evidence.XXXXXXXX")"
export EVIDENCE
phase=source-evidence
finish_evidence() {
    local code=$?
    trap - EXIT
    python3 - "$EVIDENCE" "$code" "$phase" <<'PYRESULT'
import json
from pathlib import Path
import sys
path, code, phase = sys.argv[1:]
(Path(path) / 'result.json').write_text(json.dumps({
    'build_exit_code': int(code), 'last_phase': phase,
    'scope': 'build-command-only-not-boot-or-CTS',
}, indent=2) + '\n')
PYRESULT
    exit "$code"
}
trap finish_evidence EXIT
repo manifest -r -o "$EVIDENCE/repo-manifest.xml"
repo diff > "$EVIDENCE/source-diff.patch"
python3 - "$REPO_ROOT" "$LUNCH_TARGET" "$EVIDENCE" <<'PYEVIDENCE'
import json
from pathlib import Path
import subprocess
import sys
root, target, output = sys.argv[1:]
root, output = Path(root), Path(output)
# Use the same pinning validation as delivery; do not accept branch names.
import importlib.util
spec = importlib.util.spec_from_file_location('bundle', root / 'scripts/firmware-bundle.py')
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)
bundle.pinned_manifest(output / 'repo-manifest.xml')
def git(*args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()
metadata = {'scope': 'source-snapshot-not-build-success', 'lunch_target': target,
            'doxaiz_commit': git('rev-parse', 'HEAD'),
            'doxaiz_worktree_status': git('status', '--porcelain'), 'sha256': {}}
for name in ('repo-manifest.xml', 'source-diff.patch'):
    metadata['sha256'][name] = bundle.digest(output / name)
apk = Path('vendor/doxaiz/apps/DoxaizLauncher/DoxaizLauncher.apk')
metadata['sha256']['DoxaizLauncher.apk'] = bundle.digest(apk)
(output / 'source-evidence.json').write_text(json.dumps(metadata, indent=2) + '\n')
PYEVIDENCE
echo "Source evidence (не доказательство сборки/boot): $EVIDENCE"
phase=lunch
echo "=== envsetup + lunch + m ==="
# shellcheck disable=SC1091
. build/envsetup.sh
lunch "${LUNCH_TARGET}"

echo "=== Проверяю выбранный продукт DoxaizOS ==="
# Запрашиваем вычисленные Make-переменные, а не grep по исходникам:
# наличие overlay на диске ещё не означает, что продукт его наследует.
phase=product-gates
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
phase=compile
m -j"$(nproc)"
phase=build-command-completed

echo "=== Готово. Артефакты: ${TREE}/out/target/product/ ==="
