# Архитектура DoxaizOS

Проект: **максимально лёгкая мобильная ОС для телефонов с 2 ГБ ОЗУ**. База — Android (AOSP/LineageOS) в «slim»-конфигурации; весь новый код — на Rust; рабочий стол — [Doxaiz Launcher](https://github.com/Doxaiz/Doxaiz-android-launcher-), встроенный в образ.

## 1. Принципы (в порядке приоритета)

1. **Минимум:** в образ попадает только то, без чего телефон не выполняет свои функции.
2. **Ноль лишних фоновых процессов:** каждый сервис либо нужен пользователю постоянно, либо не запускается.
3. **Свободная память важнее «фич»:** цель — ≥ 1,0 ГБ свободной RAM в состоянии покоя (см. бюджет ниже).
4. **Безопасность не продаётся за мегабайты:** SELinux enforcing, verified boot, подписи — обязательны.
5. **Rust по умолчанию:** любой новый системный компонент DoxaizOS пишется на Rust, если это не требует драйверных C-интерфейсов.
6. **Измеримость:** каждая оптимизация подтверждается замером (`adb shell`), а не верой.

## 2. Слои

```
┌───────────────────────────────────────────────────────────┐
│  Пользовательские приложения (любое APK, F-Droid и т.п.)   │
├───────────────────────────────────────────────────────────┤
│  Doxaiz Launcher — рабочий стол (HOME), каталог, шторка,  │
│  панель ОЗУ, блокировка экрана. Kotlin, MIT.              │
├───────────────────────────────────────────────────────────┤
│  Android Framework (slim): ActivityManager, PackageManager │
│  WindowManager, SystemUI (SystemUI/Go), no GMS             │
├───────────────────────────────────────────────────────────┤
│  Нативные системные сервисы AOSP (SurfaceFlinger, audio,  │
│  cameraserver, installd…) — C++, из LineageOS/AOSP        │
│  Новые сервисы DoxaizOS — Rust (см. §5)                   │
├───────────────────────────────────────────────────────────┤
│  HAL (hardware abstraction) — vendors, привязаны к SoC    │
├───────────────────────────────────────────────────────────┤
│  Linux kernel (Common Kernel): Binder, ION/dmabuf,        │
│  lowmemorykiller daemon (lmkd), ZRAM (zstd), scheduler    │
│  (schedutil), f2fs/ext4; Rust for Linux — где приняли     │
├───────────────────────────────────────────────────────────┤
│  Bootloader (загрузчик устройства, unlock + AVB)          │
└───────────────────────────────────────────────────────────┘
```

## 3. Что осознанно НЕ входит в образ

| Компонент | Замена | Эффект |
|---|---|---|
| Google Mobile Services (GMS), GApps, Play Services | нет; установка APK вручную / F-Droid | экономия ОЗУ (фоновые GMS-процессы), CPU idle и место |
| Google SetupWizard | `ro.setupwizard.mode=OPTIONAL` | первый запуск быстрее, меньше шагов |
| OEM-лаунчер / тематические демоны | Doxaiz Launcher | легче домашний экран, русский UI из коробки |
| AOSP-пасхалки, automotive/TV пакеты | удаляются на этапе синхронизации (`manifest/doxaiz.xml`) | быстрее repo sync, меньше места |
| Live wallpapers / гироскоп-обои | статичные обои | CPU/GPU вне критического пути |

## 4. Бюджет памяти (целевой, 2 ГБ ОЗУ)

Сумма проверяется на Cuttlefish и реальном устройстве через `dumpsys meminfo` и `/proc/meminfo`.

| Компонент | Целевой PSS |
|---|---|
| kernel + zram (вне пользовательского учёта) | ~250–350 МБ |
| system_server | ≤ 220 МБ |
| SystemUI (Go) | ≤ 120 МБ |
| Doxaiz Launcher (HOME) | ≤ 60 МБ |
| zygote + runtime | ≤ 60 МБ |
| **Итого система** | **≤ 700–750 МБ** |
| **Свободно (MemAvailable) ≥ 1 мин после boot** | **≥ 1,0 ГБ** |

Если замер хуже цели — сначала ужимаем фоновые процессы (не урезая функциональность), см. [PERFORMANCE.md](PERFORMANCE.md).

## 5. Где Rust

| Место | Что | Статус |
|---|---|---|
| Ядро Linux | Binder-драйвер на Rust (upstream, 2025), Ashmem | включаем когда дерево ядра устройства поддерживает CONFIG_RUST |
| AOSP platform | Bluetooth, DNS resolver, Keystore, медиа — уже Rust | наследуем вместе с AOSP, не трогаем |
| `core/crates/doxaiz-perf` | Генератор low-RAM профиля (build.prop), единственный источник истины для low-RAM свойств | в этом репо, тестами |
| `core/crates/doxaiz-xtask` | Верификация репозитория, генерация build.prop, будущие задачи релиза | в этом репо |
| `core/crates/doxaiz-metrics` | Парсеры `/proc/meminfo`, `am start -W`, `dumpsys gfxinfo`, `dumpsys meminfo <pkg>` + `doxaiz-check`: автоматическая проверка бюджетов | в этом репо, тестами |
| ROADMAP → этап 6 | `doxaiz-sys`: Binder/AIDL-сервис на Rust (память, профиль, диагностика) для лаунчера | не реализован |

## 6. Подпись и verified boot

* Release-сборки подписываются release keys устройства (`build/make/target/product/security/`); приватные ключи никогда не попадают в git (см. [SECURITY.md](SECURITY.md)).
* Разработка — `userdebug`; продуктовые ветки — `user` (root недоступен без разблокировки).
* AVB 2.0: boot/system/vendor подписаны; при первой коммерческой поставке bootloader заблокирован.

## 7. Структура репозитория

```
DoxaizOS/
├── README.md                    # обзор и быстрый старт
├── LICENSE                      # MIT
├── CHANGELOG.md                 # история изменений
├── docs/                        # вся документация (русский)
│   ├── RESEARCH.md              # исследование (что, почему, источники)
│   ├── ARCHITECTURE.md          # этот файл
│   ├── BUILD.md                 # как собрать прошивку
│   ├── PERFORMANCE.md           # low-RAM тюнинг и измерение
│   ├── SECURITY.md              # безопасность и подпись
│   ├── LAUNCHER.md              # интеграция Doxaiz Launcher
│   ├── DEVICES.md               # как выбрать телефон под DoxaizOS
│   ├── OTA.md                   # релизы и OTA-обновления (подпись, откат)
│   ├── GSI.md                   # «на любой телефон»: GSI, DSU, прошивка
│   ├── RUST-OSES.md             # готовые Rust-ОС: что тянет слабый телефон (и что нет)
│   ├── STATUS.md                # честный статус: что проверено, что нет
│   └── ROADMAP.md               # этапы и критерии готовности
├── manifest/doxaiz.xml          # локальный манифест (исключения из AOSP)
├── overlay/vendor/doxaiz/       # вендорский overlay: продукты (doxaiz_base для
│                                # per-device/Cuttlefish, doxaiz_gsi для «любой Treble-телефон»),
│                                # AndroidProducts.mk (lunch doxaiz_arm64-userdebug),
│                                # prebuilt APK, privapp-permissions, свойства low-RAM
├── core/                        # Rust workspace
│   └── crates/
│       ├── doxaiz-perf/         # low-RAM профили + gen-buildprop (тесты)
│       ├── doxaiz-xtask/        # verify репозитория, gen-prop
│       └── doxaiz-metrics/      # парсер meminfo + doxaiz-check (бюджет памяти)
├── scripts/                     # bash/python инструментарий сборки и проверки (build/preflight/ota/…)
├── assets/logo.svg              # логотип
└── .github/workflows/ci.yml     # CI: cargo test, clippy, проверка ссылок и overlay
```

## 8. Компромиссы, которые мы приняли осознанно

1. **Базовый Android API — весь, но «голый».** Мы не сокращаем HAL/фреймворк по коду (ломает совместимость приложений), мы сокращаем его по конфигурации и составу образа.
2. **PRESIGNED-режим лаунчера по умолчанию** — проще и честнее (не нужен platform key), приватных же разрешений лаунчеру не нужно; привилегированный режим — опционален.
3. **Чистый Rust вне AOSP не блокирует релиз:** Rust-инструментарий улучшает качество (тесты, CI), но ядро и runtime — из AOSP/LineageOS до тех пор, пока upstream не докажет обратное.
4. **Cuttlefish вместо эмулятора AVD** — ближе к реальному устройству (KVM, отдельный init, реальный фреймворк) и автоматизируется в CI.
5. **«На любой телефон» = GSI, а не маркетинговая фраза:** одна сборка `doxaiz_arm64` (Project Treble, Android 8+) вместо тысяч per-device портов; ядро и vendor берёт сам телефон. Чего GSI не гарантирует (камера, Widevine L1, Play Integrity, 16K-страницы) — честно перечислено в [GSI.md](GSI.md) §6; per-device порты остаются вторым контуром для лучшего поведения.
