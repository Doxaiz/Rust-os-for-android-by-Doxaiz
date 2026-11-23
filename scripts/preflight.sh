#!/usr/bin/env bash
# DoxaizOS: preflight-проверка ПК перед сборкой AOSP/LineageOS.
# Ничего не устанавливает, только смотрит и печатает вердикт.
#
#   scripts/preflight.sh [путь-к-будущему-дереву]   # по умолчанию: текущий каталог
#
# Код выхода: 0 — можно собирать; 1 — не хватает ОЗУ или не Linux; иначе предупреждения.
set -euo pipefail

TARGET="${1:-$PWD}"
warns=0
fails=0

note()  { echo "  [ok]   $*"; }
warn()  { echo "  [warn] $*"; warns=$((warns + 1)); }
fail()  { echo "  [FAIL] $*" >&2; fails=$((fails + 1)); }

echo "=== DoxaizOS preflight (AOSP/LineageOS slim) ==="

if [ "$(uname -s)" != "Linux" ]; then
    fail "нужна Linux (у вас $(uname -s))"
else
    note "Linux: $(uname -r)"
fi

arch="$(uname -m)"
case "$arch" in
    x86_64) note "архитектура: x86_64" ;;
    *) warn "архитектура $arch — официально поддерживается только x86_64 хост" ;;
esac

mem_gb=$(awk '/MemTotal/ {printf "%d", $2/1024/1024}' /proc/meminfo)
if [ "$mem_gb" -ge 24 ]; then note "ОЗУ: ${mem_gb} ГБ"
elif [ "$mem_gb" -ge 12 ]; then warn "ОЗУ: ${mem_gb} ГБ — минималка; добавьте zram/swap на хосте"
else fail "ОЗУ: ${mem_gb} ГБ — слишком мало для сборки AOSP (<12 ГБ)"; fi

df_gb=$(df -BG --output=avail "$TARGET" 2>/dev/null | tail -1 | tr -dc '0-9' || echo 0)
if [ "$df_gb" -ge 250 ]; then note "диск: свободно ~${df_gb} ГБ"
elif [ "$df_gb" -ge 120 ]; then warn "диск: ~${df_gb} ГБ — впритык для полной синхронизации+сборки"
else fail "диск: ~${df_gb} ГБ — не хватит даже для repo sync (<120 ГБ)"; fi

cores="$(nproc 2>/dev/null || echo 1)"
if [ "$cores" -ge 8 ]; then note "ядра: $cores"
elif [ "$cores" -ge 4 ]; then warn "ядра: $cores — сборка будет долгой"
else warn "ядра: $cores — соберётся, но медленно"; fi

for cmd in git python3 curl java; do
    if command -v "$cmd" >/dev/null 2>&1; then note "$cmd: $(command -v "$cmd")"
    else warn "$cmd не найден (нужен для сборки; см. docs/BUILD.md §1)"; fi
done

if command -v repo >/dev/null 2>&1; then note "repo: $(command -v repo)"
else warn "repo не найден — установка: docs/BUILD.md §2"; fi

if [ -e /dev/kvm ]; then
    if [ -r /dev/kvm ] && [ -w /dev/kvm ]; then note "/dev/kvm доступен (можно Cuttlefish)"
    else warn "/dev/kvm есть, но без прав — usermod -aG kvm \$USER && reboot"; fi
else
    warn "/dev/kvm нет — Cuttlefish не запустится (нужна KVM или реальный телефон)"
fi

echo "=== Итог: ошибок ${fails}, предупреждений ${warns} ==="
if [ "$fails" -gt 0 ]; then
    echo "Исправьте [FAIL] перед сборкой." >&2
    exit 1
fi
[ "$warns" -gt 0 ] && echo "Собрать можно, но обратите внимание на [warn]."
exit 0
