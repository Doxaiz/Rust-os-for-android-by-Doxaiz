# DoxaizOS — честный статус проекта

> Обновлено: 2026-11-23. Этот файл — ответ на вопрос «насколько готова DoxaizOS?» без приукрашивания. Правило проекта: «готово» = проверено прогоном, а не написано.

## Три уровня готовности

| Уровень | Состояние | Пояснение |
|---|---|---|
| 1. Спроектировано и написано (репозиторий) | **~90%** | docs, overlay, CI, Rust-инструментарий, манифест, скрипты |
| 2. Собирается и запускается где-то | **0%** | ни одного образа (Cuttlefish/GSI/device) не собрано |
| 3. Работает на телефоне у пользователя | **0%** | не прошивалось и не тестировалось на железе |

Сводная оценка до релиза 1.0: **~25–30%**.

## Статус по областям

| Область | Статус | Что проверено | Что нужно для «✅» |
|---|---|---|---|
| Исследование (RESEARCH, RUST-OSES, GSI) | ✅ | 58 источников с датой доступа; утверждения сверены с первоисточниками (AOSP docs, исходники LOS lineage-24.0, GitHub API) | — (поддерживаться актуальность) |
| Архитектура и бюджеты (ARCHITECTURE, PERFORMANCE) | 📄 | цифры согласованы между README/доки/`doxaiz-metrics` (400 мс / 5 % / 16 мс / 60 МБ / 1,0 ГБ / 220 МБ) | замеры на Cuttlefish и железе (Этап 4) |
| Документация (весь `docs/`) | ✅ | `check-docs-links.py` 73/73; перекрёстные ссылки согласованы | — |
| Overlay `doxaiz_base.mk` (per-device/Cuttlefish) | 📄 | синтаксис makefile; пакеты/свойства по документации AOSP | `lunch <target> && m` на ПК (Этапы 2–3) |
| Overlay `doxaiz_gsi.mk` + `AndroidProducts.mk` (GSI) | 📄 | `gsi_arm64` наследование сверено по исходникам LOS lineage-24.0 и `build/make/core/board_config.mk`; `PRODUCT_ENFORCE_ARTIFACT_PATH_REQUIREMENTS=relaxed` по образцу mgsi/* | GSI-сборка на ПК ≥ 32 ГБ ОЗУ (Этап 5, 5-GSI) |
| Локальный манифест (`manifest/doxaiz.xml`) | ✅ | валидный XML; удаления сверены с default.xml lineage-24.0 на 2026-11-23; GSI-безопасны | — |
| Rust workspace `doxaiz-perf` | ✅ | unit-тесты (в CI), граничные значения zram/heap | — |
| Rust workspace `doxaiz-metrics` | ✅ | 8 тестов; парсеры meminfo/am-start/gfxinfo/meminfo-pkg; бюджеты машинно-проверяемы | проверка на устройстве (Этапы 3–5) |
| doxaiz-xtask `verify` | ✅ | 31/31 маркер в CI | — |
| CI (GitHub Actions, 4 джобы) | ✅ | Rust test+verify, Scripts (bash -n + XML), Docs (links), Launcher APK (информативно) | — |
| Скачивание релизного APK лаунчера + sha256 | ✅ (логика) | релиз v1.0.0 существует, ассет `doxaiz-1.0.0.apk` (~854 КиБ) + `apk-sha256.txt`; хардфейл при несовпадении | e2e-прогон на машине с сетью (в песочнице запрещён TLS к release-assets) |
| Doxaiz Launcher как HOME в образе | 📄 | сверено с исходным кодом лаунчера (v1.0.0): applicationId, HOME-фильтры, без INTERNET, ~854 КиБ | сборка образа + `set-home-activity` на Cuttlefish (Этап 3) |
| Cuttlefish-прогон | ❌ | — | `launch_cvd` + чеклист BUILD.md §9 (нужен ПК с KVM) |
| GSI на реальном телефоне + DSU | ❌ | — | любой Treble-телефон (Android 10+); [GSI.md](GSI.md) §4–5 |
| Per-device порт (3–4 ГБ low-end) | ❌ | — | Xperia XA2 / Redmi Note 9/10S / Redmi 12C — [DEVICES.md](DEVICES.md) §7 |
| Подписанный OTA-релиз | 📄 | скрипт `ota.sh` (syntax OK), пайплайн описан ([OTA.md](OTA.md)) | ключи + прогон `ota_from_target_files` на реальном дереве (Этап 7) |
| Rust Binder-сервис (`doxaiz-sys`) | 🔬 | исследование rsbinder завершено (см. RESEARCH §2.2, ROADMAP этап 6) | выбор библиотеки + прототип + интеграция |
| Чистые Rust-ОС (Asterinas/moss/BlueOS и др.) | 🔬 | исследование [RUST-OSES.md](RUST-OSES.md) | — (не блокирует 1.0) |

**Условные обозначения:** ✅ проверено прогоном · 📄 написано, не проверено прогоном · 🔬 исследование · ❌ нет

## Изменения этого файла — через PR

Правки STATUS.md — только с изменением фактов («📄 → ✅» допустимо только при приложенном логе прогона/скриншоте/CI).
