# Дорожная карта DoxaizOS

> **Изменение основного направления:** сначала готовая минимальная LineageOS/TrebleDroid Vanilla и проверка её совместимости, затем небольшой слой DoxaizOS. [Решение по базе](BASE-SELECTION.md). Описанный ниже путь собственной Android 17-сборки сохранён как лабораторный; он не является предварительным условием оценки готового ROM и не подтверждает подходящий образ для Redmi.

Принцип: маленькие, измеримые этапы; ничего «на честном слове». Каждый этап имеет критерий приёмки. Порядок обязателен: 1 → 2 → 3 → 4 …

### Этап 0 — Исследование и выбор архитектуры ✅ (выполнено)

* Собраны и проанализированы варианты: AOSP slim, Android Go-модель, LineageOS, postmarketOS, чистые Rust-ОС (Afflictio/moss), Redox, Fuchsia, BlueOS.
* Решение: **LineageOS 24.0 (Android 17) + low-RAM профиль + Doxaiz Launcher + Rust для нового кода**.
* Документы: [RESEARCH.md](RESEARCH.md), [ARCHITECTURE.md](ARCHITECTURE.md).
* Критерий приёмки: письменный выбор одной архитектуры с обоснованием и отклонёнными альтернативами. ✅

### Этап 1 — Каркас репозитория и CI ✅ (выполнено в этом коммите)

* Структура: `docs/`, `manifest/doxaiz.xml`, `overlay/vendor/doxaiz/…`, `core/…` (Rust), `scripts/`, GitHub Actions.
* `doxaiz-xtask verify` проверяет целостность репозитория; `doxaiz-perf` — с тестами, генерирует low-RAM build.prop.
* Критерий приёмки: CI зелёный (cargo test, проверка ссылок, синтаксис скриптов, XML валиден).

### Этап 2 — Первая сборка для Cuttlefish (virtual phone)

* Собрать `aosp_cf_x86_64_phone` (или ближайший cuttlefish target в вашей ветке) с DoxaizOS-overlay на ПК сборщика ([BUILD.md](BUILD.md)).
* Критерий приёмки: образ собран; `launch_cvd` грузится; `adb shell getprop ro.doxaiz.version` → `0.1.0`; в `dumpsys package` присутствует `com.doxaiz.launcher`.

### Этап 3 — Doxaiz Launcher как HOME

* Включить лаунчер в образ (prebuilt, PRESIGNED), назначить HOME, прогнать smoke-чеклист из [LAUNCHER.md](LAUNCHER.md).
* Критерий приёмки: после wipe/переключателя между лаунчерами пользователь попадает на Doxaiz; каталог открывается; стрелка «назад» на HOME возвращает на рабочий стол; замер `am start -W` записан в docs.

### Этап 4 — Low-RAM профиль и замеры

* Прогнать [PERFORMANCE.md](PERFORMANCE.md) на Cuttlefish: zram 50 %, `ro.config.low_ram`, куча Dalvik, отсутствие GMS.
* Проверить бюджеты машинно: `cargo run -p doxaiz-metrics -- meminfo meminfo.txt`, `… coldstart coldstart.txt`, `… jank gfx.txt`, `… pss pss.txt` (PASS/FAIL по ARCHITECTURE.md §4).
* Снять базовые метрики: MemAvailable, PSS system_server/Launcher, холодный старт HOME, df.
* Критерий приёмки: таблица результатов добавлена в docs (значения на момент сборки), цели по памяти выполнены ≥ 80 % (или задокументировано почему нет).

### Этап 5 — Реальное устройство: per-device порт (2 ГБ ОЗУ) и универсальный GSI

* Кандидаты (проверено 2026-11-23, [DEVICES.md](DEVICES.md) §7): официальных 2 ГБ-портов не осталось (FP2/d801/m216/mt2/seed — retired); реалистичные варианты: (а) 3–4 ГБ low-end с живым портом — Redmi Note 9/10S, Xperia XA2, Redmi 12C / POCO C55; (б) 2 ГБ Treble-телефон + DoxaizOS-GSI (единственный путь, см. [GSI.md](GSI.md)); (в) unofficial 2 ГБ-сборки (quality не гарантировано).
* Unlock bootloader → прошивка → perf-тесты на железе.
* **5-GSI («на любой телефон»):** собрать `lunch doxaiz_arm64-userdebug` (доки: [GSI.md](GSI.md), продукт `overlay/vendor/doxaiz/products/doxaiz_gsi.mk` поверх LOS-таргета `gsi_arm64`); проверить на DSU (без прошивки, Android 10+, динамические разделы) минимум на 2–3 моделях разных вендоров (например Pixel + Xiaomi + Samsung), затем fastboot-сценарий с `--disable-verity`.
* Критерий приёмки: 24 ч стабильной работы без ребутов; HOME без падений; заряд за ночь ≤ 3–5 % idle; заполненная таблица PERFORMANCE.md; для 5-GSI — DSU-лог успешной загрузки как минимум на одной модели и, желательно, на двух разных вендорах.

### Этап 6 — Rust-компоненты уровня системы

* `doxaiz-sys`: Binder-сервис на чистом Rust. Практические пути (по убыванию предпочтительности):
  1. **rsbinder** ([qwq233/rsbinder](https://github.com/qwq233/rsbinder), crates.io) — pure-Rust Binder IPC для Android 10–17 (API 29–37), wire-compatible с Android libbinder; ядро/RPC транспорт; есть AIDL-компилятор. Pre-1.0: проверить лицензию, зрелость API и совместимость транзакций с целевой веткой перед продакшн-использованием.
  2. `libbinder_ndk` через C++-обёртку (не чисто Rust, но официально стабильный API NDK).
  3. In-tree сервис AOSP на Rust (если/когда AOSP соберёт у нас штатно).
* Функции сервиса: отдача PSI/MemAvailable/профиль build.prop диагностике в лаунчере (§ «панель ОЗУ» читает системный сервис, а не procfs напрямую).
* Критерий приёмки: лаунчер на устройстве показывает реальные PSI/MemAvailable через сервис; `adb shell service list | grep doxaiz` непуст.

### Этап 7 — Релиз и обновления

* `user`-сборки, release keys, подписанный OTA (LineageOS recovery) — пайплайн и чеклист: [OTA.md](OTA.md), генерация: `scripts/ota.sh`.
* CI: сборка артефактов OTA по тегу (на self-hosted runner или на ПК мейнтейнера; публичный GitHub runner для AOSP недостаточен по диску).
* Критерий приёмки: обновление по Wi-Fi поверх установленного DoxaizOS без потери данных.

### Этап 8 — Долгосрочное (исследовательское)

* Следить за Rust for Linux (Binder уже в upstream); по мере готовности включать `CONFIG_RUST` в ядре целевого устройства, если порт ядра его поддерживает.
* Проверить moss/Afflictio на прогресс: если ядро пройдёт веху «телефон реального устройства», оценить пилотный порт как отдельный трек (не блокирует 1–7).
* Возможный нативный Rust-компоновщик экрана (DRM/KMS) для fastboot-экрана — только после стабильного релиза.

## Сводка рисков → этапов

| Риск | Влияние | Митигация |
|---|---|---|
| Нет устройства с 2 ГБ и живым портом LOS | Этап 5 | Cuttlefish + low-end с большим портом; **GSI как универсальная альтернатива** (любой Treble-телефон); партнёрство с комьюнити порта |
| GSI не грузится на части моделей (camera/IMS/Widevine) | Этап 5 (5-GSI) | DSU-тест до прошивки; vndklite-вариант для Go-устройств; per-device порт для «капризных» моделей; честные ограничения в GSI.md §6 |
| Сборка AOSP ломается после апгрейда ветки | Этап 2/4 | фиксируем ветку lineage-24.0; rebase по расписанию; CI проверяет структуру |
| Лаунчер как prebuilt устаревает | Этапы 3+ | release-APK по тегам; `fetch-launcher-apk.sh` всегда тянет latest |
| low-RAM свойства ветки-специфичны | Этап 4 | значения — стартовая калибровка; имена параметров сверяем с кодом lmkd ветки |
