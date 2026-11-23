# Changelog

## [Unreleased] — 2026-11-23

### Added
* `docs/OTA.md` — релизный пайплайн: target-files → подпись → `ota_from_target_files` → sideload/A-B → откат, чеклист релиза, подводные камни.
* `scripts/ota.sh` — обёртка над `ota_from_target_files` (полная и дельта-сборки); запускается внутри дерева AOSP.
* `doxaiz-metrics::probe` — парсеры `am start -W` (TotalTime ≤ 400 мс), `dumpsys gfxinfo` (janky ≤ 5 %, p90 ≤ 16 мс), `dumpsys meminfo <pkg>` (TOTAL PSS ≤ 60 МБ). CLI: `doxaiz-check coldstart|jank|pss <файл>`.

## [0.2.0] — 2026-11-23

### Added
* `doxaiz-metrics` — Rust-крейт: парсинг `/proc/meminfo` и автоматическая проверка бюджета DoxaizOS (MemAvailable ≥ 1024 МБ, swap/zram включён). CLI: `doxaiz-check meminfo meminfo.txt`.
* `scripts/preflight.sh` — preflight-проверка ПК перед AOSP-сборкой (Linux/arch, ОЗУ, диск, ядра, repo/java/kvm).
* `docs/DEVICES.md` — как выбрать телефон под DoxaizOS (критерии, методика, Cuttlefish как запасной вариант).
* `docs/PERFORMANCE.md` — раздел «Автопроверка бюджета» с командами.
* CI: шаг `cargo clippy` (информативно, не блокирует сборку); джоба `launcher-prebuilt` (валидирует релизный APK лаунчера).

### Changed
* `doxaiz-perf`: граничные тесты (2049/3073 МиБ, zram 512 МБ на 1 ГБ устройстве).
* `doxaiz-xtask verify`: проверки метрик, DEVICES, CHANGELOG, preflight, ota.sh.
* `docs/ARCHITECTURE.md`, `README.md`, `docs/ROADMAP.md` — состав репозитория дополнен новыми компонентами.

## [0.1.0] — 2026-11-23

Первая публикация: исследование, архитектура, вендорский overlay, low-RAM профиль (build.prop), интеграция Doxaiz Launcher как prebuilt HOME, Rust-инструментарий (`doxaiz-perf`, `doxaiz-xtask`), CI, документация.
