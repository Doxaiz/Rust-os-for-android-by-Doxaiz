# Производительность DoxaizOS на 2 ГБ ОЗУ

Цель: максимум отзывчивости при жёстком потолке памяти и минимальное фоновое потребление. Ниже разделены настройки исходного overlay и рекомендации для ещё не собранного образа. Наличие строки в репозитории не доказывает её применение во время загрузки; **каждое** изменение требует замеров на своей сборке Cuttlefish и затем на железе.

## 1. Что уже включено в overlay DoxaizOS

`overlay/vendor/doxaiz/products/doxaiz_base.mk`:

```
ro.config.low_ram=true          # low-RAM режим фреймворка и lmkd
ro.setupwizard.mode=OPTIONAL    # не отключает штатный AOSP Provision
dalvik.vm.heapstartsize=8m
dalvik.vm.heapgrowthlimit=96m
dalvik.vm.heapsize=256m
# + блок ro.lmk.* с официальными low-RAM дефолтами AOSP (см. §3)
ro.doxaiz.version=0.1.0
ro.doxaiz.profile=lowram-2gb
```

`ro.config.low_ram=true` — главный переключатель: фреймворк сам урезает внутренние кэши, отключает часть фоновых механизмов и агрессивнее выгружает приложения. Значения кучи — стартовая калибровка для 2 ГБ; сравните с исходными low-RAM устройствами вашего SoC и корректируйте.

Генератор этих значений — `core/crates/doxaiz-perf` (с тестами). Сменить профиль:

```bash
cd core
cargo run -p doxaiz-xtask -- gen-prop --ram-mb 2048   # печатает build.prop-фрагмент
cargo test --workspace
```

## 2. ZRAM (swap в сжатом ОЗУ)

ZRAM хранит выгруженные страницы в сжатом виде в ОЗУ; реальная экономия и CPU-затраты зависят от содержимого и алгоритма. **Overlay пока не включает/не настраивает ZRAM сам**: это vendor/kernel/fstab-конфигурация конкретного продукта. Профиль Rust 50% — расчётная рекомендация, не доказательство активного swap.

У наследуемого Cuttlefish android-17.0.0_r1 `shared/config/fstab.in` уже задано **zramsize=75%**, а не наши планировочные 50%: https://android.googlesource.com/device/google/cuttlefish/+/refs/tags/android-17.0.0_r1/shared/config/fstab.in . Пока не подменяем vendor fstab ради совпадения цифры: сначала нужны /proc/swaps, disksize, mm_stat, comp_algorithm и PSI-замеры на собственной сборке. GSI не получает право менять vendor fstab Redmi автоматически.

В `fstab` устройства (например, `device/<vendor>/<model>/*.fstab` или `rootdir/fstab.*`) добавьте/проверьте строку:

```
/dev/block/zram0  none  swap  defaults  zramsize=50%
# при желании: zramsize=1024M (явный размер) или max_comp_streams=N через тот же fstab
```

Проверка на устройстве:

```bash
adb shell cat /sys/block/zram0/comp_algorithm   # активный алгоритм указан в [скобках]; zstd не гарантирован
adb shell cat /proc/swaps
```

Если устройство старое и CPU слабый — zstd может стоить больше CPU, чем даст пользы; тогда `lzo-rle`. Это не догма, это замер (`vmstat 1` до/после).

## 3. lmkd (lowmemorykiller daemon) — когда и как выгружать приложения

Современный AOSP использует `lmkd` в userspace; поведение старого vendor-ядра нельзя вывести только из номера версии. PSI-режим (Pressure Stall Information) требует поддержки ядром, включая `CONFIG_PSI=y`; требования memory cgroups/PIDFD сверяются для выбранной ветки ([исходники lmkd](https://android.googlesource.com/platform/system/memory/lmkd/+/master/README.md)).

`ro.config.low_ram=true` (наш случай) переключает lmkd на философию «система должна терпеть более высокое давление памяти как нормальный режим» ([source.android.com, lmkd](https://source.android.com/docs/core/perf/lmkd)). Точные дефолты low-RAM vs high-performance (таблица «Configure lmkd in Android 11» официального документа) **уже зафиксированы в overlay** `vendor/doxaiz/products/doxaiz_base.mk`:

| Свойство | High perf (по умолчанию) | Low RAM (DoxaizOS) | Смысл |
|---|---|---|---|
| `ro.lmk.psi_partial_stall_ms` | 70 | **200** | порог partial PSI для уведомлений о давлении |
| `ro.lmk.psi_complete_stall_ms` | 700 | **700** | порог полного простоя для критического уведомления |
| `ro.lmk.thrashing_limit` | 100 | **30** | % workingset refaults к pagecache → «thrashing» |
| `ro.lmk.thrashing_limit_decay` | 10 | **50** | %, на сколько опускается порог thrashing после kill |
| `ro.lmk.swap_free_low_percentage` | 20 | **10** | % свободного swap, ниже которого swap «голоден» |
| `ro.lmk.swap_util_max` | 100 | **100** | % занятого swap; 100 = проверка выключена |
| `ro.lmk.low` / `medium` / `critical` | 1001 / 800 / 0 | **1001 / 800 / 0** | границы oom_adj для kill-ов |
| `ro.lmk.use_psi` | true | **true** | PSI вместо vmpressure |
| `ro.lmk.kill_heaviest_task` | false | не задан | убийца берёт самый жирный подходящий процесс (включите при замере, если kill-ы «не те») |
| `ro.lmk.debug` | false | **false** | логи в logcat (включать только при отладке) |

Практические шаги:

1. Убедитесь, что PSI жив: `adb shell cat /proc/pressure/memory` — не пусто.
2. Убедитесь, что low-RAM виден фреймворком: `adb shell getprop ro.config.low_ram` → `true`; приложения увидят `ActivityManager.isLowRamDevice() == true` (и система — `isLowRamDeviceStatic()`), потому что фреймворк читает именно `ro.config.low_ram`.
3. Тюнинг — только с замером: `ro.lmk.psi_partial_stall_ms` и `thrashing_limit` — первые кандидаты. Не копируйте цифры из «твиков» с XDA (напр., `kill_heaviest_task=true` без замера).
4. Проверка kill-поведения: `adb shell dumpsys activity lru` — видно процессы и их adj-закомы; `logcat -b all | grep lmkd` — кого lmkd убивал.

## 4. F2FS и файловая система

* F2FS и ext4 сравнивать замерами fsync/GC на целевом накопителе. Не менять файловую систему/форматировать разделы телефона ради неподтверждённого обещания ускорения; `/cache` может отсутствовать.
* `/system` и `/vendor` — только read-only (ext4/erofs + dm-verity).
* `noatime` на `/data` — меньше метаданных записи.

## 5. Планировщик и частоты CPU

* `schedutil` как governor (правильные частоты зависят от нагрузки, экономит батарею в простое).
* `schedtune`/cgroups: в Android передний план получает приоритет (top-app cgroup); ничего не отключайте, но убедитесь, что устройство не «уехало» на powersave в DTS/ROM по ошибке.
* На 2 ГБ избегайте агрессивного понижения максимальной частоты больших ядер — фоновая работа будет блокировать лаунчер.

## 6. Отказ от Google-служб = самый большой выигрыш

* Нет GMS → нет `com.google.android.gms` в фоне: обычно десятки процессов, сотни МБ ОЗУ и постоянная просыпалка ради push.
* Отсутствие Google SetupWizard не отменяет штатный AOSP Provision. Для нового пользователя сначала должен корректно завершиться provisioning, затем проверяется начальный HOME DoxaizOS.
* Пользователь получает приложения через F-Droid/APK-файлы; подписанные приложения из Play при ручной установке работают как обычно (Play Services не обязательны для большинства приложений, кроме push/location в части из них).

## 7. Что вырезано на этапе синхронизации

`manifest/doxaiz.xml`: automotive (`packages/apps/Car/*`), `VirtualGamepad`, `TvFeedbackConsent`, `SampleLocationAttribution`. Это десятки репозиториев, гигабайты синхронизации и минус потенциальные фоновые пакеты.

Следующая ступень (только после стабилизации): `QuickSearchBox`, `Music/MusicFX`, `Browser2`, стандартный `Launcher3` — см. комментарии в манифесте. Каждое удаление — по одному, с проверкой Cuttlefish.

## 8. Замеры: как понять, что «стало быстрее»

```bash
# Холодный старт лаунчера:
adb shell am force-stop com.doxaiz.launcher
adb shell am start -W -a android.intent.action.MAIN -c android.intent.category.HOME
#   → TotalTime в мс; цель ≤ 400 мс

# Память системы и топ-процессов:
adb shell dumpsys meminfo | head -40
adb shell dumpsys meminfo com.doxaiz.launcher

# Свободно ОЗУ:
adb shell cat /proc/meminfo | grep -E 'MemTotal|MemFree|MemAvailable|SwapFree'

# Частота кадров и пропущенные кадры:
adb shell dumpsys gfxinfo com.doxaiz.launcher framestats
adb shell dumpsys SurfaceFlinger --latency-clear

# Батарея (что просыпается):
adb shell dumpsys batterystats | head -80

# PSI — «давление» на память/CPU/IO:
adb shell cat /proc/pressure/memory; adb shell cat /proc/pressure/cpu; adb shell cat /proc/pressure/io
```

Целевые значения: [ARCHITECTURE.md](ARCHITECTURE.md) §4. Правило: не оптимизировали то, что не замерили.

Автопроверка бюджета (без вычислений «в уме»):

```bash
# 1) память:
adb shell cat /proc/meminfo > meminfo.txt
cargo run -p doxaiz-metrics -- meminfo meminfo.txt
# 2) холодный старт HOME (предварительно force-stop):
adb shell am force-stop com.doxaiz.launcher
adb shell am start -W -a android.intent.action.MAIN -c android.intent.category.HOME > coldstart.txt
cargo run -p doxaiz-metrics -- coldstart coldstart.txt
# 3) джанки кадров (после прогона анимации/сценария):
adb shell dumpsys gfxinfo com.doxaiz.launcher > gfx.txt
cargo run -p doxaiz-metrics -- jank gfx.txt
# 4) PSS лаунчера:
adb shell dumpsys meminfo com.doxaiz.launcher > pss.txt
cargo run -p doxaiz-metrics -- pss pss.txt
# код выхода: 0 — все PASS; 1 — FAIL/ошибка; 2 — данных недостаточно (Unknown)
```

## 9. Золотые правила DoxaizOS

1. Свободный ОЗУ важнее «дополнительных функций».
2. Стабильность > 10% ускорения. Сначала — отсутствие падений, потом цифры.
3. Один параметр за раз; замер до и после; запись результата в `docs/` (добавим таблицу после первых прогонов).
4. SELinux никогда не переключаем в permissive «ради скорости» (см. [SECURITY.md](SECURITY.md)).
5. Если параметр помогает только на Cuttlefish, но вредит на железе (и наоборот) — оставляем поведение устройства, а не эмулятора.

### Достоверность результата CLI

`doxaiz-check` больше не считает отсутствие метрик успехом: код 2 означает неполный/нераспознанный вывод. Если одновременно есть FAIL и Unknown, приоритет — код 1. Скрипты должны принимать результат только при коде 0.

Для jank требуется `Total frames rendered > 0`. Нулевое количество кадров не подтверждает плавность: AOSP печатает `Janky frames: 0 (0.00%)` даже без кадров. NaN, бесконечность, отрицательные значения и проценты вне 0–100 не подтверждают бюджет.

Источник формата (проверен через GitHub API 2026-11-23): [AOSP Android 16 ProfileData.cpp](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-16.0.0_r1/libs/hwui/ProfileData.cpp), `dump`, условие `mTotalFrameCount == 0 ? 0.0f`. Regression-примеры синтетические, не результаты устройства. Проверка положительного количества кадров не гарантирует достаточную длительность или репрезентативность замера.

### Холодный старт: статус и состояние запуска

Для подтверждения бюджета `coldstart` требуются `Status: ok`, `LaunchState: COLD`, `TotalTime` и `Complete`. `Status: timeout` и строки ошибок дают FAIL (код 1); WARM/HOT/UNKNOWN, предупреждение `Activity not started` и отсутствие состояния дают Unknown (код 2), а не подтверждение холодного старта. Для старых форматов без LaunchState нужна отдельная методика: автоматически считать их холодными нельзя.

Пример синтетического валидного ввода (не замер DoxaizOS):

```text
Status: ok
LaunchState: COLD
Activity: com.doxaiz.launcher/.MainActivity
TotalTime: 213
WaitTime: 221
Complete
```

Формат и предупреждения сверены 2026-11-23 через GitHub API с `ActivityManagerShellCommand.java`: [Android 15](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-15.0.0_r1/services/core/java/com/android/server/am/ActivityManagerShellCommand.java) (blob `bbd432340e8f559d513da79207d8de92fa0020aa`) и [Android 16](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-16.0.0_r1/services/core/java/com/android/server/am/ActivityManagerShellCommand.java) (blob `5c2bd0a0e90f807cba524de2448e61216a60f282`). Наличие `Complete` само по себе не исключает timeout. Подтверждение `COLD` относится к запуску процесса/Activity, а не к очистке дисковых кэшей или репрезентативности серии измерений.

## Сбор диагностических файлов с выбранного устройства

```bash
adb devices -l
# Замените SERIAL идентификатором из adb devices; запуск на Linux-хосте:
bash scripts/collect-device.sh SERIAL reports/session-001

# Проверка файлов из корня репозитория (не запускает команды на телефоне):
cargo run --manifest-path core/Cargo.toml -p doxaiz-metrics --bin doxaiz-check -- meminfo reports/session-001/meminfo.txt
cargo run --manifest-path core/Cargo.toml -p doxaiz-metrics --bin doxaiz-check -- pss reports/session-001/pss.txt
cargo run --manifest-path core/Cargo.toml -p doxaiz-metrics --bin doxaiz-check -- jank reports/session-001/gfxinfo.txt
```

Скрипт требует явный serial, готовое авторизованное ADB-устройство, завершённую загрузку и установленный пакет `com.doxaiz.launcher`. Каждый вызов ADB ограничен 30 секундами (`timeout` из GNU coreutils). Сохраняются `/proc/meminfo`, `dumpsys meminfo com.doxaiz.launcher`, `dumpsys gfxinfo com.doxaiz.launcher` и контекст (время UTC, fingerprint, SDK, low_ram, версия DoxaizOS).

Сбор не выполняет root, установку APK, force-stop, сброс gfxinfo, reboot или прошивку. Счётчики gfxinfo накопительные: сначала проведите сценарий взаимодействия из этого документа. Coldstart намеренно не собирается автоматически — корректный холодный запуск требует отдельной подготовки и нарушил бы принцип «не останавливать HOME».

Отчёт публикуется только после успешных команд и проверки непустых файлов; существующее назначение не перезаписывается. Это **сбор сырых данных**, а не подтверждение производительности: даже непустой вывод может оказаться нераспознанным, проверяйте код выхода `doxaiz-check`. Снимки не атомарны по времени и относятся к нескольким последовательным командам.

Каталог создаётся с правами 0700; fingerprint и список приложений в meminfo могут быть чувствительными. `reports/` исключён из git; перед передачей отчёта проверьте содержимое. В другом каталоге игнорирование не гарантируется.

Форматы парсеров сопоставлены с ActivityThread/ProfileData AOSP (ссылки выше). Offline-тест `test_collect_device.py` проверяет только оркестрацию с mock adb; настоящего отчёта с телефона пока нет.

### Штатная MIUI без установленного лаунчера

```bash
bash scripts/collect-device.sh SERIAL reports/stock-001 --stock
```

В этом режиме не вызываются pm/dumpsys для Doxaiz Launcher: сохраняются `meminfo.txt`, `storage.txt` (`df -k /data`) и `context.txt`. Контекст дополнен model/device, списками 32/64-bit ABI, Treble, vendor SDK/VNDK и несколькими boot-свойствами. Пустое свойство — неизвестное значение; эти строки не являются автоматическим заключением о совместимости GSI. Свободное место не доказывает исправность eMMC. Требования Linux, GNU coreutils, авторизованного ADB и загруженного Android сохраняются; установка приложений и разблокировка не нужны.


### Примечание о PRESIGNED и dexpreopt

В нашем Android.mk сейчас явно стоит LOCAL_DEX_PREOPT=false. Это **не ограничение PRESIGNED**: [app_prebuilt_internal.mk](https://github.com/LineageOS/android_build/blob/lineage-24.0/core/app_prebuilt_internal.mk) поддерживает dexpreopt без повторной подписи presigned APK. Отключение preopt может менять стоимость первой загрузки/первого старта и место под odex/vdex; без своей сборки и замеров нельзя объявлять его оптимизацией скорости или обещать экономию памяти. В этом изменении флаг не переключался — исправлен ошибочный комментарий о невозможности AOT.

## Rust-first слой: измерять pressure, не запускать «ускоритель RAM»

По требованию пользователя новые собственные вычислительные компоненты DoxaizOS приоритетно пишутся на **Rust**. Существующие Android framework, ядро, HAL и Doxaiz Launcher не переписываются ради языка: без профиля узких мест это риск регрессий и лишний объём работ, не доказательство максимальной производительности. Host-side Python/bash build/audit scripts не работают постоянно на телефоне и сами по себе не расходуют его runtime RAM.

Первое конкретное дополнение — `doxaiz-metrics::psi`, Rust-парсер `/proc/pressure/memory` без внешних crates, `unsafe`, потоков и фонового polling. Сам parser использует заимствованные строки и фиксированные поля, не создаёт String/Vec; CLI выделяет буфер ввода не более 4097 байт. `#![forbid(unsafe_code)]` действует на библиотеку metrics. Это инженерное ограничение реализации, **не измеренный результат экономии RAM всей ОС**.

```bash
# Read-only snapshot, не настройка ядра и не сброс кэшей:
adb -s SERIAL shell cat /proc/pressure/memory > reports/memory.psi
cd core
cargo run --release -p doxaiz-metrics --bin doxaiz-check -- psi ../reports/memory.psi
```

Режим `psi` запускается по запросу и завершается. В ОС не добавляется daemon/сервис/таймер. На host анализируется снимок телефона; host binary нельзя просто скопировать в Android — Android-target/NDK/Soong packaging и runtime ещё не реализованы.

Формат сверён с [Linux PSI documentation](https://docs.kernel.org/accounting/psi.html): `some` — время, когда хотя бы часть задач stalled; `full` — когда stalled все non-idle задачи. `avg10/60/300` — проценты за окна 10/60/300 секунд; `total` — накопленные микросекунды, не свободные байты и не длительность конкретного запуска приложения.

Требуются обе строки и все четыре поля; NaN/infinity, проценты вне 0..100, дубликаты, overflow total, неизвестный/обрезанный формат дают inconclusive (CLI exit 2), не «нулевое давление». Отсутствующий PSI тоже не считается успехом. Exit 0 режима означает только **измерение распознано**, даже при avg10=99%; текст явно не заявляет performance-budget PASS. Порог PSI для DoxaizOS не придумывается без workload-baseline. `total` между разными boot нельзя сравнивать как latency, а одно значение не доказывает ускорение ROM.

Rust CI выполняет unit/CLI tests и release smoke с synthetic input, а при наличии PSI — с host Linux snapshot. Такой smoke не является benchmark Android, не измеряет Redmi и не добавляет проценты готовности. Для performance claims нужны release Android binary, одинаковая нагрузка, серии измерений CPU/PSS/PSI/latency и сравнение с неизменённой готовой базой. Security blocker выбранного prebuilt остаётся отдельным обязательным условием, Rust-парсер его не исправляет.

Подтверждённый прогон новой Rust-реализации: [CI 46170363841](https://github.com/Doxaiz/Rust-os-for-android-by-Doxaiz/actions/runs/46170363841), commit 5224ccd, **SUCCESS**, Rust job 141057158979. `cargo test`, release PSI smoke, xtask verify и profile generation завершились успешно. Clippy также помечен success, но остаётся информативным, не release gate. Содержимое host PSI snapshot/число тестов из logs локально не извлекались; конкретные значения и телефонный performance результат не заявляются. В sandbox rustc/cargo отсутствуют, реальная компиляция выполнена hosted runner, не локально.
