# Changelog

## [Unreleased] — 2026-11-23

### Added
* APK checksum теперь обязателен по умолчанию: недоступная/нечитаемая сумма — отказ с сохранением prebuilt. Явный DOXAIZ_ALLOW_UNVERIFIED_APK=1 оставлен только для разработки; build.sh его принудительно отключает. Несовпадение хеша не обходится. 7 дополнительных offline-сценариев, всего 59; проверка сертификата APK пока не реализована.
* `build.sh`: перед `m` проверяет вычисленные PRODUCT_PACKAGES/PRODUCT_PROPERTY_OVERRIDES через Soong dumpvar — модуль DoxaizLauncher, low_ram и версию DoxaizOS. При забытом наследовании overlay или ошибке dumpvar останавливается, а не выдаёт обычный Android за DoxaizOS. Добавлены 3 offline-сценария (всего 52 сценария скриптов); настоящая Android-сборка остаётся непроверенной.
* `scripts/collect-device.sh`: явный ADB serial, проверка загрузки/пакета, сбор сырых meminfo/PSS/gfxinfo и контекста без root/force-stop/прошивки; timeout 30 с на команду, приватный каталог, защита от перезаписи и неполных отчётов. 7 offline-сценариев, инструкция в PERFORMANCE.md, reports/ исключён из git. Реальных диагностических данных пока нет.
* `coldstart`: по AOSP Android 15/16 добавлены Status/LaunchState и распознавание ошибок/повторного использования Activity. Timeout/ошибка — FAIL, warm/hot/неизвестное состояние — Unknown; быстрый TotalTime + Complete больше не подтверждает холодный старт сам по себе. 2 unit-теста и CLI-тест с 7 сценариями; примеры и источники в PERFORMANCE.md.
* `doxaiz-check`: Unknown теперь даёт код 2 вместо ложного успеха; FAIL сохраняет код 1. Для gfxinfo пустая выборка кадров, NaN/Inf/отрицательные метрики не проходят бюджет. Проверено поведение нулевой выборки в AOSP ProfileData.cpp; добавлены 2 unit-теста и 4 CLI integration-теста (12 сценариев).
* `doxaiz-metrics`: по исходникам ActivityThread Android 15/16 исправлен PSS-парсер — поддержка таблицы `TOTAL` без двоеточия и сводки `TOTAL PSS:`, исключение RSS/SWAP, приоритет явной PSS-сводки. Добавлены 5 regression-тестов и 2 синтетические source-derived фикстуры с происхождением; это не замеры устройства.
* `build.sh`: абсолютный путь дерева до cd, local manifest до первого sync (одна синхронизация вместо двух). 6 offline-сценариев связки build → overlay → APK → lunch → m, включая ошибки этапов и пути с пробелами. Это не сборка Android.
* OTA: по примерам AOSP/LineageOS заменён рекурсивный поиск и python3-вызов на прямой запуск host releasetools с явным выбором пути; добавлены `DOXAIZ_OTA_KEY`, staging, проверка ZIP/метаданных и защита исходных файлов. 8 offline-сценариев; исправлен пример sign_target_files_apks (`-o -d <каталог>`), источники сравнения записаны в OTA.md. Реальная OTA-сборка/подпись не выполнялась.
* `cuttlefish-run.sh`: ожидание полной загрузки Android с таймаутом, проверка наличия adb/пакета и назначения HOME без маскировки ошибок; адрес подключения исправлен на loopback. 8 offline-сценариев оркестрации добавлены в существующий unittest discovery CI. Реальный запуск Cuttlefish не выполнен.
* Offline regression-тесты загрузчика APK: 20 сценариев (gh и API), включая неверный хеш, повреждённый ZIP/CRC, отсутствие dex, ошибки загрузки, сохранность старого APK и очистку. Запуск unittest включён в обязательный Scripts job CI; эти тесты не подтверждают работоспособность APK на Android.
* `docs/OTA.md` — релизный пайплайн: target-files → подпись → `ota_from_target_files` → sideload/A-B → откат, чеклист релиза, подводные камни.
* `scripts/ota.sh` — обёртка над `ota_from_target_files` (полная и дельта-сборки); запускается внутри дерева AOSP.
* `doxaiz-metrics::probe` — парсеры `am start -W` (TotalTime ≤ 400 мс), `dumpsys gfxinfo` (janky ≤ 5 %, p90 ≤ 16 мс), `dumpsys meminfo <pkg>` (TOTAL PSS ≤ 60 МБ). CLI: `doxaiz-check coldstart|jank|pss <файл>`.
* overlay `doxaiz_base.mk`: явный блок `ro.lmk.*` с **официальными low-RAM дефолтами AOSP** (документация source.android.com/docs/core/perf/lmkd; psi_partial_stall_ms=200, thrashing_limit=30, thrashing_limit_decay=50, swap_free_low_percentage=10).
* `docs/RESEARCH.md`: 10 новых источников (lmkd-документация AOSP, lmkd README, rsbinder, LineageOS wiki: требования по ОЗУ/диску lineage-21+ → 64 ГБ / 400 ГБ, синтаксис `<remove-project>`, Project Svelte); новый раздел «2.2а Официальная механика low-RAM в Android».
* `docs/BUILD.md`: таблица требований по версиям LineageOS + раздел ccache (25–50 ГБ, вторая сборка в разы быстрее).
* `docs/PERFORMANCE.md` §3: полная таблица low-RAM дефолтов lmkd с источниками и признаки работы PSI/low-RAM на устройстве.
* `scripts/fetch-launcher-apk.sh`: проверка sha256 релизного APK по `apk-sha256.txt` (hard fail при несовпадении; предупреждение при недоступности) — сверено по актуальному релизу лаунчера (v1.0.0, ассет `doxaiz-1.0.0.apk`).
* `docs/STATUS.md` (новый): честная матрица готовности — 3 уровня (~90% написано / 0% собирается / 0% телефонов), по областям с условными ✅📄🔬❌ и что нужно для «✅»; README и дерево ARCHITECTURE обновлены; verify +1 маркер.
* `docs/DEVICES.md` §7 (новое, 2026-11-23): **официальных maintained 2 ГБ-портов LineageOS больше нет** (FP2/d801/m216/mt2/seed — retired; Jetson Nano 2GB = Android TV); минимальный поддерживаемый класс — 3–4 ГБ (Xperia XA2, Redmi Note 9/10S, Redmi 12C/POCO C55); для железных 2 ГБ единственный путь — DoxaizOS-GSI. RESEARCH риск №1 уточнён; ROADMAP Этап 5 переписан (3–4 ГБ порт ИЛИ 2 ГБ + GSI); источники [55]–[58]; RESEARCH [1][2] актуализированы (Afflictio GPL-3.0; moss → hexagonal-sun).
* `docs/RUST-OSES.md` (новый): готовые Rust-ОС на 2026-11 — таблица (Android+Rust [база], BlueOS/BlueKernel Vivo [32 МБ, серийно, не чужое железо], Tock/Xous/Hubris [микроконтроллеры], Redox [x86_64/i686, aarch64 RPi 3B+], Asterinas [x86_64 VM-only], moss-kernel [Pi4/Nano/Kria, 109 syscalls], Theseus [заглохла], RustyHermit→hermit-os/hermit-rs); вывод: готовой Rust-ОС для слабого телефона нет — рабочий путь = AOSP-slim с Rust (DoxaizOS); источники [45]–[54]; ARCHITECTURE/README обновлены; verify +2 маркера.
* `docs/LAUNCHER.md`: блок «проверено по исходному коду лаунчера» (дата доступа 2026-11-23, `main`@v1.0.0) — applicationId, minSdk 26/targetSdk 34, HOME-фильтр, отсутствие `INTERNET`, размер релизного APK (873 735 Б), CI лаунчера на API 34; RESEARCH [21] дополнен теми же фактами.
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

### Дополнительное усиление загрузчика APK

* Загрузка закреплена за определённым тегом; временный каталог изолирован и очищается через trap. APK заменяется атомарно только после проверки доступного хеша и структуры ZIP (manifest + classes.dex + CRC). При несовпадении хеша старый prebuilt сохраняется.
* Локальные offline smoke-тесты с подменёнными curl/gh: корректный хеш и несовпадение — PASS; это не сетевой e2e и не проверка подписи APK. Отсутствующий checksum по-прежнему вызывает предупреждение, а не подтверждение целостности.
* STATUS: уточнены ограничения локального link-check, исследования и совместимости DSU; проценты обозначены субъективными оценками.
