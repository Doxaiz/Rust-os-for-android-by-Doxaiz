# Участие в разработке DoxaizOS

Коротко и по делу.

## Рабочий процесс

1. Ветка от `main` (`feature/...`, `fix/...`), в `main` — только через PR.
2. Коммиты — осмысленные, с телом, объясняющим «почему».
3. PR должен проходить CI (`.github/workflows/ci.yml`): Rust-тесты, проверка ссылок в docs, синтаксис shell-скриптов, валидность XML.
4. Никаких бинарников и секретов: APK, OTA, keystore — мимо git (см. `.gitignore`).

## Документация — часть продукта

* Изменил поведение — обнови соответствующий файл в `docs/`.
* Утверждения о производительности — только с командой замера и результатом (см. PERFORMANCE.md).
* Новые ссылки в `docs/RESEARCH.md` — только живые, с датой доступа.
* Трогаешь `overlay/vendor/doxaiz/` — пропусти через `doxaiz-xtask verify`; новый standalone-продукт регистрируй в `AndroidProducts.mk` (иначе `lunch` его не покажет).

## Сборка и проверка

```bash
# Быстрая локальная проверка (не нужны AOSP и железо):
(cd core && cargo test --workspace && cargo run -p doxaiz-xtask -- verify)
python3 scripts/check-docs-links.py
python3 -m unittest discover -s scripts/tests -v

# Полная сборка прошивки — docs/BUILD.md (ПК сборщика).
```

## Что делать НЕ нужно

* Переводить SELinux в permissive «для удобства».
* Коммитить прошивки, ключи, APK.
* Менять ветку базы (`lineage-24.0`) без обновления BUILD.md и описания рисков.
* «Оптимизировать» замерами эмулятора то, что относится к железу.

## Код стиля

Rust — `rustfmt` (stable), `cargo clippy` по возможности; shell — `set -euo pipefail`, кавычки везде; python — stdlib only.
