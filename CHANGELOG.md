# Changelog

## [Unreleased] — 2026-11-23

### Added
* `docs/OTA.md` — релизный пайплайн: target-files → подпись → `ota_from_target_files` → sideload/A-B → откат, чеклист релиза, подводные камни.
* `scripts/ota.sh` — обёртка над `ota_from_target_files` (полная и дельта-сборки); запускается внутри дерева AOSP.
* `doxaiz-metrics::probe` — парсеры `am start -W` (TotalTime ≤ 400 мс), `dumpsys gfxinfo` (janky ≤ 5 %, p90 ≤ 16 мс), `dumpsys meminfo <pkg>` (TOTAL PSS ≤ 60 МБ). CLI: `doxaiz-check coldstart|jank|pss <файл>`.
* overlay `doxaiz_base.mk`: явный блок `ro.lmk.*` с **официальными low-RAM дефолтами AOSP** (документация source.android.com/docs/core/perf/lmkd; psi_partial_stall_ms=200, thrashing_limit=30, thrashing_limit_decay=50, swap_free_low_percentage=10).
* `docs/RESEARCH.md`: 10 новых источников (lmkd-документация AOSP, lmkd README, rsbinder, LineageOS wiki: требования по ОЗУ/диску lineage-21+ → 64 ГБ / 400 ГБ, синтаксис `<remove-project>`, Project Svelte); новый раздел «2.2а Официальная механика low-RAM в Android».
* `docs/BUILD.md`: таблица требований по версиям LineageOS + раздел ccache (25–50 ГБ, вторая сборка в разы быстрее).
* `docs/PERFORMANCE.md` §3: полная таблица low-RAM дефолтов lmkd с источниками и признаки работы PSI/low-RAM на устройстве.
* `scripts/preflight.sh`: пороги по официальным требованиям LineageOS (ОЗУ ≥ 32 ГБ ok / 64 wiki, диск ≥ 400 ГБ), проверка ccache.
* `docs/GSI.md` — **«прошивка на любой телефон»**: DoxaizOS-GSI (универсальный system.img для Project Treble, Android 8+): требования/проверка устройства за 30 секунд, сборка `lunch doxaiz_arm64-userdebug`, fastboot-рецепт (обязательный `--disable-verity` для vbmeta), безопасный тест через DSU (Dynamic System Updates, Android 10+, dynamic partitions, ≥ 40 % свободного места), честный список ограничений (камера/Widevine L1/Play Integrity/16K-страницы), матрица «GSI vs per-device vs Cuttlefish vs DSU».
* overlay `doxaiz_gsi.mk` + `AndroidProducts.mk` — продукт **doxaiz_arm64** (наследует LOS-таргет `gsi_arm64` из `device/generic/common`, `PRODUCT_DEVICE=generic_arm64`, + `doxaiz_base.mk`; `PRODUCT_ENFORCE_ARTIFACT_PATH_REQUIREMENTS=relaxed` по образцу штатной mgsi/* — иначе CTS-проверка путей отвергнет prebuilt-лаунчер): универсальная сборка, видна в `lunch` после `apply-overlay.sh`.
* `docs/RESEARCH.md`: раздел «2.4. GSI — как одна прошивка ставится на любой телефон» (VNDK, DSU, верити, vndklite для Go-устройств); источники [34]–[44] (официальные GSI Android 17, AOSP GSI/vts-инструкция, DSU, TrebleDroid/phhusson, AndyYan).
* `docs/ROADMAP.md` Этап 5 переписан: два контура — per-device порт и **5-GSI** (DSU-тест на ≥ 2 моделях разных вендоров); раздел рисков дополнен сценарием «GSI не грузится на части моделей».
* `docs/BUILD.md` §8.3 (GSI-сборка), §11 (указатель на GSI-рецепт), §12 (симптомы GSI в таблице); `docs/DEVICES.md` — два пути поставки (GSI vs per-device); `docs/SECURITY.md` — vbmeta `--disable-verity` только для неподписанного GSI; `docs/OTA.md` — область действия per-device vs GSI (обновление GSI = перепрошивка system.img).
* `README.md` — GSI как путь №1 «поставить на любой телефон»; `doxaiz-xtask verify` — маркеры GSI (docs/GSI.md, doxaiz_gsi.mk, AndroidProducts.mk).

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
* `docs/ROADMAP.md`, `docs/RESEARCH.md` — этап 6 переписан: `doxaiz-sys` на rsbinder (pure-Rust Binder, Android 10–17; альтернативы libbinder_ndk / in-tree Rust); состав репозитория дополнен новыми компонентами.

## [0.1.0] — 2026-11-23

Первая публикация: исследование, архитектура, вендорский overlay, low-RAM профиль (build.prop), интеграция Doxaiz Launcher как prebuilt HOME, Rust-инструментарий (`doxaiz-perf`, `doxaiz-xtask`), CI, документация.
