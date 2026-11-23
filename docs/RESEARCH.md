# Исследование: как сделать максимально лёгкую мобильную ОС на Rust

*DoxaizOS — исследование на 2026-11-23. Все ссылки проверены на дату публикации.*

## 1. Короткие выводы

| # | Вывод | Почему |
|---|-------|--------|
| 1 | **База — Android (AOSP/LineageOS), сборка «slim».** Не «с нуля». | Реальному телефону нужны драйверы (GPU, модем, камера, Wi-Fi, PMIC): их написание с нуля — годы работы и отдельная ветка на каждую модель. Android даёт их готовыми, и это единственный путь к «поставить на телефон с 2 ГБ ОЗУ» в разумный срок. [12][19] |
| 2 | **Рабочий стол — Doxaiz Launcher** ([репозиторий](https://github.com/Doxaiz/Doxaiz-android-launcher-)), встроенный в образ как системное приложение с ролью HOME. | Готовый, проверенный в CI на эмуляторе Android 14 рабочий стол на Kotlin; подходит 1:1. [21] |
| 3 | **Rust — для всех новых компонентов DoxaizOS** (здесь и в дереве AOSP). | Rust официально поддержан в AOSP с 2021; с 2026 новые security-critical компоненты Android пишутся на Rust по умолчанию; Rust for Linux принят в mainline и с декабря 2025 больше не считается «экспериментом». [4][5][6][7] |
| 4 | **Лёгкость берём по модели Android Go:** `ro.config.low_ram`, маленькие лимиты кучи Dalvik, ZRAM 50 %, lmkd (с официальными low-RAM дефолтами), отказ от Google-служб, удаление automotive/TV-пакетов. | Android Go — официальная «облегчённая» Android-модель ровно под класс устройств ≤ 2 ГБ / 16 ГБ; на практике ~вдвое компактнее полного Android. Дефолты lmkd для low-RAM задокументированы AOSP. [13][14][15][24][25] |
| 5 | **ОС с нуля на чистом Rust (как Afflictio/moss) — отслеживаем, но не выбираем для 2 ГБ-телефона сегодня.** | Такие проекты уже грузятся в QEMU и пишутся на Rust, но до реальных драйверов и пригодности для 2 ГБ-железа — долгая дистанция; сам проект Afflictio честно маркирует себя «загружаемым скелетом». [1][2][3] |
| 6 | **Проверка — Cuttlefish (виртуальный телефон AOSP) + CI.** Реальный билд — на ПК сборщика, не в песочнице. | Cuttlefish — официальный способ AOSP прогнать образ в VM и через adb; KVM есть на GitHub Actions/обычном ПК. [17][18] |
| 7 | **«Поставить на любой телефон» = GSI-сборка (Project Treble, Android 8+).** Per-device порт — второй контур для лучшего поведения. | GSI (Generic System Image) — официальный формат Google «один system.img на тысячи моделей»; DSU позволяет протестировать GSI без прошивки (Android 10+, динамические разделы). Подробно: [GSI.md](GSI.md), §2.4. [34][39][43] |

Отвечая на главный вопрос «какая архитектура даст максимум производительности и позволит ставить даже на 2 ГБ ОЗУ с большим запасом свободной памяти»:

**Lean AOSP/LineageOS (без GMS, low-RAM-профиль, ядро Common Kernel + ZRAM) + Doxaiz Launcher как HOME + весь новый код на Rust — поставляемый как GSI для всех Treble-устройств (плюс per-device порты).** Точные целевые бюджеты — в [ARCHITECTURE.md](ARCHITECTURE.md), методика замеров — в [PERFORMANCE.md](PERFORMANCE.md).

---

## 2. Что уже существует в мире (и чему у них учиться)

### 2.1. Операционные системы и ядра на Rust

* **Afflictio** — мобильная ОС для AArch64: ядро Linux + userspace на Rust; грузится в QEMU, собственные init/shell; GPL-3.0, активна, статус «скелет». [1][5][54]
* **moss** (hexagonal-sun/moss-kernel, бывший hardliner66/moss) — Linux-совместимое Unix-like ядро на Rust + AArch64 asm: MMU AArch64, SMP/EEVDF, 109 syscalls; грузит Arch Linux aarch64 (bash, BusyBox, coreutils, strace); проверено на Raspberry Pi 4, Jetson Nano, AMD Kria, i.MX8; MIT, ~2k★. Сеть (TCP/IP) и полноценная ФС — в разработке. [2][3][48]
* **Redox OS** — микроядерная ОС на Rust: 0.9.0 (2025), x86_64 «golden», i686 «generally working», aarch64 experimental (RPi 3B+ до shell; начальный SMP для aarch64); рабочий стол Orbital; USB mass-storage в разработке; телефоном не цель. 16.7k★. [8][49]
* **Fuchsia** (Google) — капабилити-микроядро Zircon (C/C++/Rust), для телефонов не заявлена; важна как источник идей (компоненты, capabilities). [9]
* **BlueOS (BlueKernel, Vivo)** — единственная «настоящая» Rust-ОС в серии: ядро на Rust с 2018, открыто 2025-07-31 (Apache-2.0, 1.4k★; ARM32/ARM64/RISCV32/RISCV64; QEMU; 32 МБ ОЗУ заявлено); BlueOS 2 (окт 2024) — «first fully Rust-written OS»; серийно на Vivo Watch и ИИ-терминалах, НЕ на телефонах и не для чужого железа. [10][46][47]
* **Rust-ядра совместимости с Linux:** Asterinas (MPL-2.0; framekernel, 240+ syscalls, 0.19.0: DRM, **AArch64 как 4-я архитектура**, Asterinas NixOS; x86_64 VM-only — на реальном железе не запускать), Maestro (AGPL), Kerla (MIT/Apache-2.0) — все без драйверной базы телефона. [3][45]
* **Xous** (betrusted.io) — чистый Rust микроядро (message-passing), работает на Baochip-1x (400 МГц Vexriscv, 2 МиБ SRAM, открытый кремний) — самый «минимальный» живой Rust-ОС-пример; телефонные SoC/модем — нет. Apache-2.0, ~1k★. [50]
* **Tock** — embedded RTOS для Cortex-M/RISC-V, от 64 КБ ОЗУ (RP2040, микросхемы, сенсоры); MIT/Apache; 6.5k★. Не телефон. [51]
* **Hubris** (Oxide) — микроядро deeply-embedded (платежи/манагеры); MPL-2.0; 3.6k★; в продакшене Oxide. Не телефон. [52]
* **Theseus** — исследовательская SAS/SPL ОС на safe Rust; MIT; заглохла с 2024-09. Не телефон. [53]
* Полный разбор «Rust-ОС vs слабый телефон» — [RUST-OSES.md](RUST-OSES.md).

**Урок:** «ОС на чистом Rust» для телефона существует только как исследовательский скелет либо как серийная ОС с жёсткой привязкой к железу производителя (BlueOS — только устройства Vivo). Главная проблема не ядро и не язык, а **драйверы и HAL**: GPU, модем, камера, сенсоры, аудио, PMIC. Поэтому DoxaizOS не изобретает ядро, а берёт готовое (Linux + AOSP/LineageOS) и пишет весь новый слой на Rust.

### 2.2. Rust внутри Android и Linux — это больше не эксперимент

* AOSP поддерживает Rust с 2021; Rust используется в Bluetooth-стеке, DNS resolver, keystore, медиа. [6]
* По обзорным оценкам, к 2023 в AOSP больше миллиона строк Rust. [18]
* Android Common Kernel 6.12 — первое ядро с включённой поддержкой Rust и первым production Rust-драйвером (Android); Google ожидает миллионы устройств на Rust for Linux. [7]
* Декабрь 2025, Linux Kernel Developers Summit / LPC: Rust в ядре официально перестал быть «экспериментом»; Binder-драйвер на Rust принят в upstream; Rust-драйверы: ASIX PHY, Tyr GPU, QR panic и др. [4][5]
* Для юзерспейс-сервисов на Rust готов **rsbinder** (pure Rust Binder/AIDL, Android 10–17, wire-compatible с libbinder; transports: kernel /dev/binder и RPC-over-socket). Pre-1.0, зрелость оценивать перед продакшном — используем на Этапе 6 ([ROADMAP.md](ROADMAP.md)). [27][28]

**Урок:** мы не «тянем Rust в консервативное ядро», а следуем официальному курсу Google и mainline.

### 2.2а. Официальная механика low-RAM в Android (базис всех решений DoxaizOS)

* `ro.config.low_ram=true` — главный переключатель: фреймворк читает его в `ActivityManager.isLowRamDeviceStatic()`; приложения видят `ActivityManager.isLowRamDevice()` и отключают тяжёлые фичи сами (механика тянется с «Project Svelte», Android 4.4). [30][33]
* **lmkd** (юзерспейс, с ядра 4.12; PSI с Android 10): для low-RAM устройств AOSP документирует свою колонку дефолтов — `psi_partial_stall_ms=200` (vs 70), `thrashing_limit=30` (vs 100), `thrashing_limit_decay=50` (vs 10), `swap_free_low_percentage=10` (vs 20), `psi_complete_stall_ms=700`. Требуются `CONFIG_PSI=y`, memory cgroups и PIDFD; `ro.config.low_ram=true` также переключает kill-стратегию lmkd («терпеть давление памяти как норму»). [24][25]
* Сборка low-RAM образа — обычные `PRODUCT_PROPERTY_OVERRIDES` в device makefile; примеры продакшн-конфигов сообщества (Dalvik heap 8/64/128, скрытие multiuser, отключение blur) показывают типовой порядок величин. [30][31]
* Всё это применяется в overlay DoxaizOS явно: см. `overlay/vendor/doxaiz/products/doxaiz_base.mk` (блок lmkd) и [PERFORMANCE.md](PERFORMANCE.md) §1/§3.

### 2.3. Лёгкие Android-сборки и альтернативы

| Вариант | ОЗУ для комфорта | Android-приложения | Итог для 2 ГБ |
|---|---|---|---|
| Стоковый Android / вендорская прошивка | 3–6+ ГБ | ✅ | ❌ тормоза, 100–300 МБ жрёт лаунчер вендора |
| **Android Go** (официальная модель) | **2 ГБ (минимум с Android 13)** | ✅ (Lite-версии) | ✅ концепция, но закрыта под GMS/OEM-сертификацию |
| **LineageOS (чистый AOSP)** | 2–3 ГБ | ✅ | ✅ **база DoxaizOS**, 200+ устройств, без bloat |
| GrapheneOS | 3+ ГБ (Pixel-only) | ✅ | ❌ тяжёл и привязан к Pixel |
| postmarketOS / Mobian / Plasma Mobile | 1–2 ГБ | ❌ (Linux-приложения) | ❌ ваш Doxaiz Launcher не запустится |
| Чистый Rust (Afflictio/moss) | теоретически < 500 МБ | ❌ | ❌ нет драйверов и API |
| Sailfish / Tizen / HarmonyOS | 2–4 ГБ | частично/✅ | ❌ закрытые экосистемы |

Источники по лёгким сборкам и Android Go: [12][13][14][15][16][19][20]
Источники по GSI/DSU («прошивка на любой телефон»): [34][35][36][37][38][39][40][41][42][43][44]
Источники по Rust-ОС (в т.ч. «на самый слабый телефон»): [45][46][47][48][49][50][51][52][53][54] — разбор в [RUST-OSES.md](RUST-OSES.md)

**Android Go — ключевое доказательство**, что 2 ГБ достаточно, если убрать всё лишнее: требования Android 13 Go — 2 ГБ ОЗУ и 16 ГБ хранилища; Android 11 требовал 1 ГБ; Android 8.1 — 512 МБ. Оптимизации: `ro.config.low_ram`, лимиты Dalvik, hibernate неиспользуемых приложений, Lite-приложения. [13][14][15]

**LineageOS** выбран как база: открытый исходный код (зеркало AOSP + LineageOS на GitHub — можно собирать с `github.com/LineageOS/android`), официальные недельные сборки, регулярные патчи безопасности, поддержка 200+ устройств, минимум предустановок, легко «отрезается» лишнее. [19][20]

Проверено по официальному манифесту: ветка `lineage-24.0` фиксирует AOSP на `refs/tags/android-17.0.0_r1` (Android 17); `device/google/cuttlefish` входит в манифест — можно собирать виртуальный телефон и гонять adb в VM (KVM). [19] Официальная wiki сборки: для ветки ≥ lineage-21 рекомендуется 64 ГБ ОЗУ и 400 ГБ диска (lineage-21+ / Android 14+); для повторных сборок — `ccache` на 25–50 ГБ. [29] Исключения из синхронизации оформляются локальным манифестом тегом `<remove-project name="…"/>` — см. [manifest/doxaiz.xml](../manifest/doxaiz.xml). [32]

### 2.4. GSI — как одна прошивка ставится на любой телефон

* **Project Treble (Android 8+, обязателен для новых устройств)** — разделил платформу и вендорские драйверы через VNDK и стабильные HAL. Поэтому Google публикует **GSI (Generic System Image)** — «голый» `/system` без привязки к железу: ядро и vendor остаются от самого телефона, образ один на тысячи моделей. [34][43]
* В `lineage-24.0` готовый GSI-набор лежит в проекте `device/generic/common` (`LineageOS/android_device_generic_common`, ветка lineage-24.0): `gsi_arm64.mk` (CTS-grade GSI, `PRODUCT_DEVICE=generic_arm64` → BoardConfig из AOSP-проекта `device/generic/arm64/BoardConfig.mk`), `mgsi_*`/`csi_*` (минимальная GSI, `PRODUCT_DEVICE=dummy_arm64` → `device/generic/common/dummy_arm64/BoardConfig.mk`), x86/x86_64-варианты; паттерн поиска — `find -L device -maxdepth 4 -path '*/$(TARGET_DEVICE)/BoardConfig.mk'` (проверено по `build/make/core/board_config.mk` AOSP). Официальная инструкция AOSP: `lunch gsi_arm64-userdebug` → `out/target/product/generic_arm64/system.img`. [43]
* **DSU (Dynamic System Updates)** — запуск GSI без прошивки: Android 10+, динамические разделы, ≥ 40 % свободного места; образ `/data/gsi`, sandbox, stock-система не трогается; GSI должна быть не ниже stock по security patch level. [39][40]
* **Сообщество** (TrebleDroid/phhusson-патчи, сборки AndyYan `*-gsi_arm64_*` на Android 17) — рабочие GSI для LOS-подобных систем; чистые Google GSI = инструмент совместимости, не полноценные прошивки; для Android Go без VNDK-библиотек — `vndklite`-варианты. [41][42][44]
* **verity**: все Android 10+ из коробки с dm-verity → перед прошивкой своего GSI обязательно `fastboot --disable-verity --disable-verification flash vbmeta vbmeta.img` (см. [GSI.md](GSI.md) §4).
* **Ограничения**: телефоны без Treble — только per-device порт; банковские приложения / Widevine L1 / camera-HAL на «капризных» моделях — типичные проблемы GSI; 16K-страницы на Android 15+ требуют соответствующей сборки. DoxaizOS-GSI покрывает «любой Treble-телефон», а per-device LOS-порты дают лучшее поведение на конкретной модели — обе дорожки в репозитории. Полностью: [GSI.md](GSI.md).

**Урок:** GSI — единственный в индустрии механизм «одна прошивка на любой телефон»; мы строим DoxaizOS-GSI (`overlay/vendor/doxaiz/products/doxaiz_gsi.mk`, lunch `doxaiz_arm64-userdebug`) поверх LOS-GSI и DSU-тест перед прошивкой. Это и есть ответ на «поставить на любой телефон».

---

## 3. Почему именно такая архитектура (и что отвергнуть)

### 3.1. Отвергнуто: «ОС с нуля на Rust для 2 ГБ-телефона»
* Afflictio/moss загружаются в QEMU, но: нет драйверов GPU/камеры/модема/Wi-Fi ни для одного коммерческого телефона; нет совместимости с Android-приложениями; нет HALs; пользователь потеряет экосистему приложений, включая ваш лаунчер. [1][2][3]
* Даже если бы драйверы появились, 2 ГБ ОЗУ — узкое место не ядра, а пользовательского ПО, и тут выигрывает зрелая low-RAM конфигурация Android, а не «свой» userland.
* Оставляем это направление только как долгосрочный исследовательский трек (см. ROADMAP, этап 8) — без блокирования основного пути.

### 3.2. Отвергнуто: «поставить postmarketOS и переписать лаунчер под Wayland»
* Ваш лаунчер — Android-приложение (Kotlin). На Linux-без-Android он не запустится без огромной переделки. [21]
* Потеря: звонки/SMS-стек на большинстве моделей, банковские приложения, Android-экосистема. [12]

### 3.3. Отвергнуто: «GrapheneOS как база»
* Отлично по безопасности, но Pixel-only (нет 2 ГБ Pixel), и мы хотим свою сборку с нулевым доверием к GMS, а не чужую форк-модель. [20]

### 3.4. Выбрано: **DoxaizOS = LineageOS/AOSP slim + low-RAM профиль + Doxaiz Launcher + Rust для нового кода**
* Низкий порог: 2 ГБ ОЗУ, 16 ГБ хранилища — класс Android Go. [13][14]
* Лёгкость: нет GMS (магистрали фоновой активности и ~200–400 МБ ОЗУ — оценка, проверяется в [PERFORMANCE.md](PERFORMANCE.md)), нет bloat, часть AOSP-репозиториев исключена на этапе синхронизации (`manifest/doxaiz.xml`: automotive/TV пакеты).
* Быстрый старт: Cuttlefish в VM на ПК; реальное устройство — с официальным портом LineageOS. [17][18][19]
* Ваш лаунчер становится «рабочим столом ОС» без переделки. [21]
* Безопасность: SELinux enforcing + verified boot остаются нетронутыми (см. [SECURITY.md](SECURITY.md)) — сознательно не жертвуем безопасностью ради мегабайт.

---

## 4. Бюджет производительности (цели, честно про замеры)

Целевые показатели для устройства с 2 ГБ ОЗУ (проверяются на Cuttlefish и на реальном железе; это цели, а не обещания):

| Метрика | Цель DoxaizOS | Типичный стоковый Android 13 (2 ГБ) |
|---|---|---|
| Свободно ОЗУ через 1 мин после загрузки | ≥ 1.0–1.1 ГБ | 0.6–0.9 ГБ |
| PSS system_server (dumpsys meminfo) | ≤ 220 МБ | 250–350 МБ |
| Холодный старт лаунчера (am start -W) | ≤ 400 мс | 500–900 мс |
| Образ system (без userdata) | ≤ 2.5 ГБ | 3.5–5 ГБ |
| Пакетов в образе (без зависимостей) | минимальный обязательный набор | 60–120 пакетов |
| Перезапуск лаунчера после OOM | обязателен (activity-отображение «воскресенье») | часто |

Методика и команды замера — [PERFORMANCE.md](PERFORMANCE.md); что именно оптимизируем и почему — [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 5. Риски и честные ограничения

1. **«Любой телефон» = любой телефон с Project Treble (Android 8+).** DoxaizOS-GSI ставится на всю такую технику через fastboot/DSU ([GSI.md](GSI.md)), но на «капризных» моделях камера/Widevine/VoLTE могут работать хуже, чем в per-device порте; банковские приложения не пройдут Play Integrity; загрузчик нужно разблокировать (стирание данных). Без Treble — только per-device порт LineageOS под конкретную модель (или Cuttlefish для разработки). Рекомендация: DSU-тест на целевой модели → затем прошивка.
2. **Первая сборка AOSP — это 60–90 ГБ синхронизации и 3–6 часов компиляции** на 16 потоках; ветки меняются, возможны мелкие сломки — CI их не ловит, ловит только локальный билд (раздел «Где собирать» в [BUILD.md](BUILD.md)).
3. **low-RAM свойства и версия ветки привязаны:** значения `ro.lmk.*` и лимиты Dalvik — стартовая калибровка; имена параметров различаются между ветками Android; калибруем только по замерам.
4. **PRESIGNED-подпись лаунчера** = HOME-роль без привилегий; для полного привилегированного режима нужен platform key (раздел «Подпись platform-ключом» в [LAUNCHER.md](LAUNCHER.md)).
5. **DoxaizOS — форк конфигурации, а не форк Android.** Безопасность и исправления приходят из LineageOS/AOSP; наша ценность — минимализм, профиль low-RAM, интеграция лаунчера и Rust-инструментарий.

---

## 6. Источники

24. Low memory killer daemon (официальная документация AOSP: PSI, конфигурация lmkd в Android 10/11, колонки дефолтов high-perf vs low-RAM) — https://source.android.com/docs/core/perf/lmkd
25. lmkd README (Googlesource, master; колонки дефолтов low-RAM: psi_partial_stall 200, swap_free_low 10, thrashing 30/50) — https://android.googlesource.com/platform/system/memory/lmkd/+/master/README.md
26. lmkd README (зеркало LineageOS, валидация на живой ROM) — https://github.com/LineageOS/android_system_memory_lmkd/blob/lineage-20.0/README.md
27. rsbinder (crates.io): pure-Rust Binder/AIDL, Android 10–17 — https://crates.io/crates/rsbinder ; обзор: https://lib.rs/crates/rsbinder
28. rsbinder — репозиторий, статусы совместимости (API 29–37, RPC v1/v2) — https://github.com/qwq233/rsbinder
29. LineageOS Wiki — Building for Emulator/AVD (требования по ОЗУ/диску по веткам: lineage-21+ → 64 ГБ / 400 ГБ; ccache 25–100 ГБ) — https://wiki.lineageos.org/emulator
30. Low RAM Configuration (зеркало официального документа Android 4.4: `PRODUCT_PROPERTY_OVERRIDES += ro.config.low_ram=true`, `ActivityManager.isLowRamDevice()`) — https://riptutorial.com/android/example/28282/low-ram-configuration
31. LowRAM-Flag-Plus (сообщество; пример продакшн-конфига low-RAM: heap 8/64/128, disable blur/multiuser) — https://github.com/JosFlix7/LowRAM-Flag-Plus/blob/Android-Go-Tweaks/system.prop
32. Локальные манифесты: `<remove-project name="…"/>` (пример: Galaxy-MSM8916/local_manifests) — https://github.com/Galaxy-MSM8916/local_manifests/blob/master/lineage-14.1.xml
33. Tuning Android for low RAM (слайды Google, 2014; «Project Svelte» — историческая основа low_ram и isLowRamDevice) — https://2net.co.uk/slides/android-lowmemory-abs-2014.pdf
34. Generic System Image releases — официальные GSI Android 17 (vanilla и +GMS, ARM64/x86_64) — https://developer.android.com/topic/generic-system-image/releases
35. Let's clone & build AOSP Android 17 (сборка AOSP/GSI; vbmeta --disable-verity; erase system; release-config lunch) — https://goyaljai.medium.com/lets-clone-build-aosp-android-17-659554404340
36. Build & Flash custom AOSP GSI (vbmeta disable-verity; fastbootd; `m systemimage vbmetaimage`) — https://proandroiddev.com/building-flashing-a-custom-aosp-gsi-on-pixel-arm64-android-16-1313b4211c53
37. XDA: Build AOSP GSI from source + flash with DSU (gzip system.img; adb push; VerificationActivity intent) — https://xdaforums.com/t/build-aosp-gsi-from-source-and-flash-it-with-dsu.4749904/
38. DSU Sideloader (F-Droid; Android 10+; unlocked bootloader; dynamic partitions; ≥ 40 % свободного места) — https://f-droid.org/packages/vegabobo.dsusideloader/
39. Dynamic System Updates deep dive (/data/gsi, sandbox, dynamic partitions, KEY_SYSTEM_SIZE/USERDATA_SIZE) — https://archive.ph/FsuMj
40. Android 11 DSU Loader (родной DSU в Developer Options; для неподписанных GSI нужен unlocked bootloader) — https://lg-g4-xda.blogspot.com/2020/03/android-11s-dsu-loader-makes-it-easier.html
41. TrebleDroid GSI list (LineageOS 24.0 GSI от Aizner/AndyYan, Android 17) — https://github.com/TrebleDroid/treble_experimentations/wiki/Generic-System-Image-%28GSI%29-list
42. AndyYan GSI builds (aosp-pure-userdebug / lineage-*-gsi_arm64, Android 17) — https://sourceforge.net/projects/andyyan-gsi/files/aosp-pure-userdebug/
43. AOSP — Generic system images (официально: GSI-таргеты, `lunch gsi_arm64-userdebug`, out/target/product/generic_arm64/system.img) — https://source.android.com/docs/core/tests/vts/gsi
44. TrebleDroid — treble_experimentations (phhusson-патчи, vndklite для Go-устройств, GSI README) — https://github.com/TrebleDroid/treble_experimentations
45. Asterinas (MPL-2.0): 0.19.0 (2026-10) — DRM, AArch64 (4-я архитектура), Asterinas NixOS; framekernel, 240+ syscalls; x86_64 VM-only — https://github.com/asterinas/asterinas ; https://asterinas.github.io/book/
46. BlueKernel (Vivo, Apache-2.0), открыт 2025-07-31: ARM32/ARM64/RISCV32/RISCV64, QEMU; минимальная конфигурация ядра — 13 КБ ОЗУ; POSIX-совместим, rust-std, слой абстракции драйверов на Rust; системные фреймворки BlueOS тоже на Rust — https://github.com/vivoblueos/kernel ; https://opennet.ru/63649-blueos
47. BlueOS: BlueOS 2 (2024-10) «first fully Rust-written OS»; серийно на Vivo Watch 3 / ИИ-терминалах / IoT; 32 МБ ОЗУ заявлено — https://en.wikipedia.org/wiki/BlueOS
48. moss-kernel (HexagonalSun, MIT): 109 syscalls, SMP/EEVDF, Arch aarch64, Pi4/Jetson Nano/Kria/i.MX8 — https://github.com/hexagonal-sun/moss-kernel
49. Redox 0.9.0: x86_64 (golden), i686, aarch64 экспериментально (RPi 3B+); livedisk.iso — https://os.watch/redox/0.9.0
50. Xous + Baochip-1x (400 МГц Vexriscv, 2 МиБ SRAM) — 39c3: https://media.ccc.de/v/39c3-xous-a-pure-rust-rethink-of-the-embedded-operating-system
51. Tock OS (MIT/Apache-2.0): Cortex-M/RISC-V, ≥ 64 КБ ОЗУ — https://github.com/tock/tock
52. Hubris (Oxide, MPL-2.0) — https://github.com/oxidecomputer/hubris ; RustyHermit → hermit-os/hermit-rs (unikernel, Apache-2.0) — https://github.com/hermit-os/hermit-rs
53. Theseus (MIT, заглох 2024-09) + каталог Rust-ОС — https://github.com/theseus-os/Theseus ; https://github.com/flosse/rust-os-comparison
54. Afflictio (GPL-3.0): Linux-ядро + Rust userspace, скелет — https://github.com/mel0k1/Afflictio

1. Afflictio — Mobile OS in Rust on the moss kernel — https://github.com/mel0k1/Afflictio
2. moss — Rust Linux-compatible kernel (MIT) — https://github.com/hardliner66/moss
3. moss: a Linux-compatible kernel written in Rust (OSNews, 2025-11) — https://www.osnews.com/story/143918/moss-a-linux-compatible-kernel-written-in-rust/
4. Rust for Linux — https://en.wikipedia.org/wiki/Rust_for_Linux
5. LPC 2025 — Rust for Linux (PDF, включая «Binder на Rust в upstream» и «Android 6.12 — ядро с production Rust-драйвером») — https://lpc.events/event/19/contributions/2068/attachments/1859/3981/2025-12-11%20-%20LPC%202025%20-%20Rust%20for%20Linux.pdf
6. Android Open Source Project now supports Rust (SD Times, 2021-04-07) — https://sdtimes.com/softwaredev/android-open-source-project-now-supports-rust/
7. Google Security Blog — Rust in Android: move fast, fix things (2025-11) — https://security.googleblog.com/2025/11/rust-in-android-move-fast-fix-things.html
8. Redox (operating system) — https://en.wikipedia.org/wiki/Redox_(operating_system)
9. Fuchsia (operating system) — https://en.wikipedia.org/wiki/Fuchsia_(operating_system)
10. OSNews archive 2025-07: Vivo BlueOS (Rust-ядро) — https://www.osnews.com/story/date/2025/07/
11. Comparison of mobile operating systems (Wikipedia) — https://en.wikipedia.org/wiki/Comparison_of_mobile_operating_systems
12. LineageOS vs postmarketOS — https://www.saashub.com/compare-lineageos-vs-postmarketos
13. Google увеличивает требования Android 13 (Go): 2 ГБ ОЗУ / 16 ГБ (GIGAZINE, 2022-10) — https://gigazine.net/gsc_news/en/20221020-android-13-go-edition/
14. Android 11 (Go) и 2 ГБ как потолок обычного Android (GSMArena, 2020-07) — https://www.gsmarena.com/google_will_prevent_lowram_phones_from_using_android_11-news-44387.php
15. Android Go today: status, differences, requirements — https://en.androidayuda.com/where-is-android-go/ ; те же требования: https://electronics.alibaba.com/buyingguides/android-go-edition-a-practical-guide-for-budget-devices
16. Lightweight Android ROMs for old phones (Pixel Experience GO и аналоги) — https://www.fintechshield.co.in/post/top-lightweight-custom-rom-for-old-android-phones
17. Cuttlefish — Android Emulator for AOSP (source.android.com/setup) — https://source.android.com/docs/setup/start
18. Cuttlefish getting started / гайд на русском-английском (включая branch aosp-main-throttled, aosp_cf_arm64_only_phone) — https://medium.com/@aruncse2k20/launch-cattlefish-aosp-033b59d446a4 ; официально: https://android.googlesource.com/device/google/cuttlefish/
19. LineageOS/android — официальный манифест (проверено: ветка lineage-24.0 → AOSP refs/tags/android-17.0.0_r1; источник: default.xml) — https://github.com/LineageOS/android
20. 9 лучших кастомных прошивок 2025 (LineageOS как «самый легковесный чистый опыт») — https://classicalit.com/best-custom-roms-for-android/ ; сравнение ОС — https://en.wikipedia.org/wiki/Comparison_of_mobile_operating_systems
21. Doxaiz Launcher — рабочий стол DoxaizOS (репозиторий, MIT) — https://github.com/Doxaiz/Doxaiz-android-launcher- ; проверено по `main` @ v1.0.0 (2026-11-23): applicationId `com.doxaiz.launcher`, minSdk 26 / targetSdk 34, intent-filter `MAIN`+`HOME`, без `INTERNET`, релизный APK ~854 КиБ + `apk-sha256.txt`, CI на эмуляторе API 34
22. Rust for Android App Developers: обзор состояния Rust в Android (обзорный источник; цифра «1+ млн строк Rust к 2023») — https://extensionbooster.net/blog/rust-android-app-development-when-to-use-jni-ndk-guide/
23. Google Go / Android Go на 250 млн устройств (Android 13 Go) — The Verge via Gigazine — https://gigazine.net/gsc_news/en/20221020-android-13-go-edition/
