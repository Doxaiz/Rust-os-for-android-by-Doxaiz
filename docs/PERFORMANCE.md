# Производительность DoxaizOS на 2 ГБ ОЗУ

Цель: максимум отзывчивости при жёстком потолке памяти и минимальное фоновое потребление. Всё нижеперечисленное — рабочие приёмы Android Go/low-RAM, применённые к DoxaizOS; **каждое** изменение калибруется замерами на Cuttlefish и затем на железе.

## 1. Что уже включено в overlay DoxaizOS

`overlay/vendor/doxaiz/products/doxaiz_base.mk`:

```
ro.config.low_ram=true          # low-RAM режим фреймворка и lmkd
ro.setupwizard.mode=OPTIONAL    # без Google-мастера настройки
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

На 2 ГБ zram важнее любых sysctl: холодные страницы приложений сжимаются zstd и не уходят на флеш.

В `fstab` устройства (например, `device/<vendor>/<model>/*.fstab` или `rootdir/fstab.*`) добавьте/проверьте строку:

```
/dev/block/zram0  none  swap  defaults  zramsize=50%
# при желании: zramsize=1024M (явный размер) или max_comp_streams=N через тот же fstab
```

Проверка на устройстве:

```bash
adb shell cat /sys/block/zram0/comp_algorithm   # ожидание: lzo-rle [zstd]
adb shell cat /proc/swaps
```

Если устройство старое и CPU слабый — zstd может стоить больше CPU, чем даст пользы; тогда `lzo-rle`. Это не догма, это замер (`vmstat 1` до/после).

## 3. lmkd (lowmemorykiller daemon) — когда и как выгружать приложения

Android с ядра 4.12 не использует in-kernel LMK driver; вместо него — `lmkd` в юзерспейсе. С Android 10 он работает в режиме **PSI** (Pressure Stall Information): ядро компилируется с `CONFIG_PSI=y`, а low-RAM требует ещё **memory cgroups** и **PIDFD** ([исходники lmkd](https://android.googlesource.com/platform/system/memory/lmkd/+/master/README.md)).

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

* `/data` и `/cache` на F2FS (не ext4) на флеше — меньше GC-пауз, быстрее fsync (SQLite лаунчера заметно отзывчивее).
* `/system` и `/vendor` — только read-only (ext4/erofs + dm-verity).
* `noatime` на `/data` — меньше метаданных записи.

## 5. Планировщик и частоты CPU

* `schedutil` как governor (правильные частоты зависят от нагрузки, экономит батарею в простое).
* `schedtune`/cgroups: в Android передний план получает приоритет (top-app cgroup); ничего не отключайте, но убедитесь, что устройство не «уехало» на powersave в DTS/ROM по ошибке.
* На 2 ГБ избегайте агрессивного понижения максимальной частоты больших ядер — фоновая работа будет блокировать лаунчер.

## 6. Отказ от Google-служб = самый большой выигрыш

* Нет GMS → нет `com.google.android.gms` в фоне: обычно десятки процессов, сотни МБ ОЗУ и постоянная просыпалка ради push.
* Нет SetupWizard → первый запуск сразу на HOME DoxaizOS.
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
