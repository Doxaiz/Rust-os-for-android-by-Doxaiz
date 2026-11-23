# Производительность DoxaizOS на 2 ГБ ОЗУ

Цель: максимум отзывчивости при жёстком потолке памяти и минимальное фоновое потребление. Всё нижеперечисленное — рабочие приёмы Android Go/low-RAM, применённые к DoxaizOS; **каждое** изменение калибруется замерами на Cuttlefish и затем на железе.

## 1. Что уже включено в overlay DoxaizOS

`overlay/vendor/doxaiz/products/doxaiz_base.mk`:

```
ro.config.low_ram=true          # low-RAM режим фреймворка
ro.setupwizard.mode=OPTIONAL    # без Google-мастера настройки
dalvik.vm.heapstartsize=8m
dalvik.vm.heapgrowthlimit=96m
dalvik.vm.heapsize=256m
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

Android больше не использует старый собственный lmk-драйвер в общем случае; вместо него — `lmkd` в юзерспейсе, который читает PSI (Pressure Stall Information) и убивает приложения по приоритетам.

Практические шаги:

1. Убедитесь, что PSI включён: `adb shell cat /proc/pressure/memory` — должно быть не пусто.
2. Параметры lmkd задаются свойствами `ro.lmk.*` (состав и значения различаются между ветками Android — **не копируйте чужие цифры вслепую**). В вашей ветке смотрите:
   ```bash
   grep -rn "ro.lmk" system/core/lmkd* system/memory* frameworks/base/... 2>/dev/null | head
   # и документация: cs.android.com/android/platform/superproject — поиск «lmkd»
   ```
3. Смысл параметров: ниже пороги «swap свободен» → lmkd раньше убивает фоновые приложения, сохраняя передний план живым. На low-RAM устройствах это правильно: лучше перезапуск фона, чем убийство вами открытого приложения.

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

## 9. Золотые правила DoxaizOS

1. Свободный ОЗУ важнее «дополнительных функций».
2. Стабильность > 10% ускорения. Сначала — отсутствие падений, потом цифры.
3. Один параметр за раз; замер до и после; запись результата в `docs/` (добавим таблицу после первых прогонов).
4. SELinux никогда не переключаем в permissive «ради скорости» (см. [SECURITY.md](SECURITY.md)).
5. Если параметр помогает только на Cuttlefish, но вредит на железе (и наоборот) — оставляем поведение устройства, а не эмулятора.
