<div align="center">

<img src="assets/logo.svg" alt="DoxaizOS" width="220">

# DoxaizOS

**Самая лёгкая мобильная ОС для Android-телефонов: минимум ос, максимум свободной памяти.**
Android-база (LineageOS/AOSP slim) · low-RAM профиль в духе Android Go · рабочий стол — [Doxaiz Launcher](https://github.com/Doxaiz/Doxaiz-android-launcher-) · весь новый системный код — на Rust.

[![CI](https://github.com/Doxaiz/Rust-os-for-android-by-Doxaiz/actions/workflows/ci.yml/badge.svg)](https://github.com/Doxaiz/Rust-os-for-android-by-Doxaiz/actions/workflows/ci.yml)
[![Лицензия](https://img.shields.io/badge/лицензия-MIT-blue)](LICENSE)
[![База](https://img.shields.io/badge/AOSP-17%20(LineageOS%2024.0)-3ddc84?logo=android&logoColor=white)](docs/BUILD.md)

</div>

## Зачем

Телефоны с **2 ГБ ОЗУ** сегодня получают тяжёлые вендорские прошивки, которые съедают до половины памяти на «сервисы». DoxaizOS отдаёт пользователю его собственную память: без Google Mobile Services, без лишних фоновых процессов, с системным low-RAM профилем и рабочим столом, который не мешает.

**Целевые показатели (2 ГБ ОЗУ; методика — [docs/PERFORMANCE.md](docs/PERFORMANCE.md)):**

| Метрика | Цель |
|---|---|
| Свободный ОЗУ через 1 мин после загрузки | ≥ 1,0 ГБ |
| PSS system_server | ≤ 220 МБ |
| Холодный старт HOME | ≤ 400 мс |
| Размер system-образа | ≤ 2,5 ГБ |

> Честно: это цели, подтверждённые замерами на Cuttlefish/железе, а не маркетинг. Первая проверка — на Cuttlefish, затем на реальном устройстве ([docs/ROADMAP.md](docs/ROADMAP.md)).

## Быстрый старт

1. **Сборка образа** (нужен ПК, ≥ 250 ГБ SSD, Linux x86_64):
   [docs/BUILD.md](docs/BUILD.md) — от `repo init` до `launch_cvd` и `adb install`.
2. **Что внутри и почему так**: [docs/RESEARCH.md](docs/RESEARCH.md) (исследование, источники) и [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
3. **Лаунчер как HOME**: [docs/LAUNCHER.md](docs/LAUNCHER.md).
4. **Список этапов работ**: [docs/ROADMAP.md](docs/ROADMAP.md).

Одной командой инструментарий сборки (проверки репозитория):

```bash
cd core
cargo test --workspace
cargo run -p doxaiz-xtask -- verify
```

Проверить бюджет памяти реального устройства (сохраняет `meminfo.txt` из adb):

```bash
adb shell cat /proc/meminfo > meminfo.txt
cargo run -p doxaiz-metrics -- meminfo.txt   # PASS/FAIL по бюджету из docs/ARCHITECTURE.md §4
```

## Состав репозитория

```
docs/          документация: RESEARCH, ARCHITECTURE, BUILD, PERFORMANCE, SECURITY, LAUNCHER, ROADMAP, DEVICES
manifest/      локальный манифест для дерева AOSP/LineageOS (исключения automotive/TV)
overlay/       вендорский overlay vendor/doxaiz: low-RAM свойства, prebuilt лаунчера, подпись
core/          Rust workspace: doxaiz-perf (low-RAM профиль), doxaiz-xtask (проверки),
               doxaiz-metrics (бюджет памяти: парсер meminfo + doxaiz-check)
scripts/       apply-overlay.sh, fetch-launcher-apk.sh, build.sh, preflight.sh, cuttlefish-run.sh, check-docs-links.py
assets/        логотип
.github/       CI: Rust-тесты, clippy (информативно), проверка ссылок, синтаксис скриптов, валидность XML
```

## Что уже готово и что нет (честно)

| Область | Состояние |
|---|---|
| Исследование, архитектура, low-RAM профиль | ✅ готово (этот релиз) |
| Вендорский overlay + интеграция лаунчера как prebuilt | ✅ готово (PRESIGNED; platform key — [docs/LAUNCHER.md](docs/LAUNCHER.md)) |
| Rust-инструментарий с тестами и CI | ✅ готово |
| Автопроверка бюджета памяти (`doxaiz-check`) | ✅ готово |
| Первый образ Cuttlefish с DoxaizOS | ⏳ не собран (нужен ПК; смотрите BUILD.md) |
| Сборка для реального устройства с 2 ГБ | ⏳ нет (нужен официальный порт LineageOS; см. ROADMAP этап 5) |
| Чистая Rust-ОС с нуля (Afflictio/moss) | 🔭 исследовательский трек, не блокирует основную линию |

## FAQ

**Это «своё ядро с нуля»?** Нет. Для телефона с живыми драйверами и вашим лаунчером ядро с нуля на Rust сегодня проигрывает Linux+AOSP. Подробные аргументы: [docs/RESEARCH.md](docs/RESEARCH.md), §3.1.

**Куда ставить?** На Cuttlefish (разработка) и на телефон с официальным портом LineageOS (2 ГБ ОЗУ и живой порт — проверяйте [lineageos.org/devices](https://lineageos.org/devices/)).

**Будет ли Google Play?** Нет, GMS в образе нет. Приложения — APK/F-Droid. Это осознанный выбор ([docs/SECURITY.md](docs/SECURITY.md)).

**Почему Rust?** AOSP с 2021 на Rust (Bluetooth, DNS, keystore, медиа); ядро Linux ≥ 6.12 имеет Rust Binder и production Rust-драйвер; новые компоненты Android пишутся на Rust по умолчанию. DoxaizOS продолжает эту линию: [docs/RESEARCH.md](docs/RESEARCH.md), §2.2.

## Лицензия

[MIT](LICENSE). База — AOSP/LineageOS (Apache-2.0 и др.), Doxaiz Launcher — MIT.
