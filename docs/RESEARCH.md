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

Отвечая на главный вопрос «какая архитектура даст максимум производительности и позволит ставить даже на 2 ГБ ОЗУ с большим запасом свободной памяти»:

**Lean AOSP/LineageOS (без GMS, low-RAM-профиль, ядро Common Kernel + ZRAM) + Doxaiz Launcher как HOME + весь новый код на Rust.** Точные целевые бюджеты — в [ARCHITECTURE.md](ARCHITECTURE.md), методика замеров — в [PERFORMANCE.md](PERFORMANCE.md).

---

## 2. Что уже существует в мире (и чему у них учиться)

### 2.1. Операционные системы и ядра на Rust

* **Afflictio** — мобильная ОС на Rust для AArch64 поверх ядра **moss**. Грузится в QEMU, монтирует ext4, поднимает сеть (smoltcp + DHCP), есть свой init и shell, proof-of-concept композитор. MIT. Честный статус: «загружаемый скелет». [1]
* **moss** (hardliner66/moss) — Unix-like Linux-совместимое ядро на Rust и AArch64-ассемблере: MMU AArch64, CoW, slab-аллокатор, ~51 Linux-syscall, запускает BusyBox/bash, тесты 230+. Проверено на Raspberry Pi 4, Jetson Nano, AMD Kria, imx8. Лицензия MIT. [2][3]
* **Redox OS** — микроядерная Unix-like ОС на Rust; рабочий стол Orbital; к телефонам как к цели не приблизился. [8]
* **Fuchsia** (Google) — капабилити-микроядро Zircon (C/C++/Rust), для телефонов не заявлена; важна как источник идей (компоненты, capabilities). [9]
* **BlueOS** (Vivo) — Rust-ядро, используется на устройствах компании; подтверждение, что Rust в мобильных ядрах — серийная практика. [10]
* **Rust-ядра совместимости с Linux:** Asterinas (MPL), Maestro (AGPL), Kerla (MIT/Apache-2.0) — активные проекты, но все без драйверной базы телефона. [3]

**Урок:** «ОС на чистом Rust» для телефона существует только как исследовательский скелет. Главная проблема не ядро и не язык, а **драйверы и HAL**: GPU, модем, камера, сенсоры, аудио, PMIC. Поэтому DoxaizOS не изобретает ядро, а берёт готовое (Linux + AOSP/LineageOS) и пишет весь новый слой на Rust.

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

**Android Go — ключевое доказательство**, что 2 ГБ достаточно, если убрать всё лишнее: требования Android 13 Go — 2 ГБ ОЗУ и 16 ГБ хранилища; Android 11 требовал 1 ГБ; Android 8.1 — 512 МБ. Оптимизации: `ro.config.low_ram`, лимиты Dalvik, hibernate неиспользуемых приложений, Lite-приложения. [13][14][15]

**LineageOS** выбран как база: открытый исходный код (зеркало AOSP + LineageOS на GitHub — можно собирать с `github.com/LineageOS/android`), официальные недельные сборки, регулярные патчи безопасности, поддержка 200+ устройств, минимум предустановок, легко «отрезается» лишнее. [19][20]

Проверено по официальному манифесту: ветка `lineage-24.0` фиксирует AOSP на `refs/tags/android-17.0.0_r1` (Android 17); `device/google/cuttlefish` входит в манифест — можно собирать виртуальный телефон и гонять adb в VM (KVM). [19] Официальная wiki сборки: для ветки ≥ lineage-21 рекомендуется 64 ГБ ОЗУ и 400 ГБ диска (lineage-21+ / Android 14+); для повторных сборок — `ccache` на 25–50 ГБ. [29] Исключения из синхронизации оформляются локальным манифестом тегом `<remove-project name="…"/>` — см. [manifest/doxaiz.xml](../manifest/doxaiz.xml). [32]

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

1. **Ни один коммерческий телефон не «пойдёт сам по себе» от DoxaizOS без порта.** Нужен официальный порт LineageOS для конкретной модели (или Cuttlefish для разработки). Список устройств с 2 ГБ и официальным портом сужается — выбор за пользователем; рекомендация: Cuttlefish → затем устройство с живым LOS-портом.
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
21. Doxaiz Launcher — рабочий стол DoxaizOS (репозиторий, MIT) — https://github.com/Doxaiz/Doxaiz-android-launcher-
22. Rust for Android App Developers: обзор состояния Rust в Android (обзорный источник; цифра «1+ млн строк Rust к 2023») — https://extensionbooster.net/blog/rust-android-app-development-when-to-use-jni-ndk-guide/
23. Google Go / Android Go на 250 млн устройств (Android 13 Go) — The Verge via Gigazine — https://gigazine.net/gsc_news/en/20221020-android-13-go-edition/
