# Сборка DoxaizOS

DoxaizOS — это «slim-профиль» поверх LineageOS/AOSP: свой overlay, свой рабочий стол, low-RAM свойства. Поэтому сборка = обычная сборка LineageOS 24.0 + один overlay.

> Сборка и запуск — разные задачи. Для актуальной AOSP документация указывает 64 ГБ RAM и 400 ГБ свободного диска на сборщике. Готовый Cuttlefish-комплект можно запускать на отдельном меньшем KVM-хосте: [FIRMWARE-LAB.md](FIRMWARE-LAB.md). В этой песочнице собственная прошивка не собрана; существующий Android Emulator job проверяет приложение на штатном Android, не наш образ.

## 0. Проверка окружения

Проще всего — автоматически:

```bash
scripts/preflight.sh ~/doxaiz-os
```

Требования по официальным данным LineageOS (чем новее ветка, тем тяжелее сборка, [wiki](https://wiki.lineageos.org/emulator)):

| Ветка | ОЗУ (рекомендация) | Диск |
|---|---|---|
| lineage-17.1 (Android 10) | 16 ГБ | 200 ГБ |
| lineage-18.1 (Android 11) | 32 ГБ+ | 300 ГБ |
| lineage-21+ (Android 14+), вкл. lineage-24.0/Android 17 | **64 ГБ** | **400 ГБ** |

На меньшей памяти собирается дольше (вплоть до суток) — помогает zram/swap на хосте и `ccache` (ниже). Практичный минимум: 32 ГБ ОЗУ и 300+ ГБ SSD; `preflight.sh` предупреждает мягче: FAIL < 12 ГБ/быстрого диска, в остальном warn.

Либо вручную:

```bash
nproc                       # ≥ 8 (лучше 16)
free -g                     # ≥ 16 ГБ (лучше 32–64)
df -h .                     # ≥ 300 ГБ свободно (лучше 400)
python3 --version           # 3.8+
git --version
```

### ccache — вторая сборка в разы быстрее

```bash
sudo apt install -y ccache
export USE_CCACHE=1
ccache -M 50G          # дерево LineageOS огромно; 25–100 ГБ — норма
ccache -z              # статистика до сборки
```

По данным wiki, `ccache` на 25–50 ГБ сокращает часы повторной сборки до десятков минут.

## 1. Пакеты системы (Ubuntu 22.04+/Debian 12)

```bash
sudo apt update
sudo apt install -y git git-core curl gnupg flex bison gperf build-essential \
  zip unzip rsync python3 python3-pip libncurses5 libgl1-mesa-dev \
  libxml2-utils xsltproc zlib1g-dev libdw-dev lz4 screen schedtool \
  ccache e2fsprogs android-sdk-platform-tools-common
```

## 2. Инструмент `repo`

```bash
mkdir -p ~/bin
curl -o ~/bin/repo https://storage.googleapis.com/git-repo-downloads/repo
chmod a+x ~/bin/repo
export PATH="$HOME/bin:$PATH"
```

## 3. Инициализация дерева (LineageOS 24.0 ↔ Android 17)

```bash
mkdir -p ~/doxaiz-os && cd ~/doxaiz-os
repo init -u https://github.com/LineageOS/android.git -b lineage-24.0 --depth=1
```

* Проверено по официальному `default.xml` ветки `lineage-24.0`: AOSP пришпилен к `refs/tags/android-17.0.0_r1`.
* `--depth=1` критично: история AOSP не нужна и занимает десятки гигабайт.
* Синхронизация может занять 1–4 часа и ~60–90 ГБ.

## 4. Синхронизация

```bash
repo sync -c --no-tags --optimized-fetch --prune -j$(nproc)
```

Если сеть рвётся: перезапустите ту же команду — `repo` доводит дерево до согласованного состояния.

## 5. Кладём локальный манифест DoxaizOS

```bash
mkdir -p .repo/local_manifests
cp /path/to/Rust-os-for-android-by-Doxaiz/manifest/doxaiz.xml .repo/local_manifests/doxaiz.xml
repo sync -c --no-tags --optimized-fetch --prune -j$(nproc)
```

Манифест исключает automotive/TV-пакеты (они в образе телефона не нужны). Он **не** удаляет лаунчер AOSP: сначала встроим Doxaiz Launcher, убедимся, что HOME работает, и только потом осознанно удалим стандартный лаунчер (см. комментарии в файле).

## 6. Подключаем overlay DoxaizOS

```bash
/path/to/Rust-os-for-android-by-Doxaiz/scripts/apply-overlay.sh ~/doxaiz-os
```

Скрипт копирует `overlay/vendor/doxaiz` → `vendor/doxaiz` и напоминает про следующий шаг — добавить **одну строку** в product make-файл вашего целевого устройства. Для Cuttlefish (виртуальный телефон AOSP) целевой файл — product make того target, который вы собираете (например, `device/google/cuttlefish/…mk` — найдите его так):

```bash
grep -r "PRODUCT_NAME" device/google/cuttlefish/*.mk device/google/cuttlefish/**/*.mk 2>/dev/null | head
```

Добавьте в нужный `…_phone.mk` (рядом с остальными `inherit-product`):

```makefile
$(call inherit-product, vendor/doxaiz/products/doxaiz_base.mk)
```

Для реального устройства — то же самое: строка в `device/<vendor>/<model>/<model>_<release>.mk`.

Альтернатива без правки файлов устройства: сборка с `TARGET_PRODUCT`-обёрткой, где вы сами наследуете и устройство, и overlay (для этого заведите свой `vendor/doxaiz/products/doxaiz_cf_phone.mk`, который наследует product вашего устройства; путь подставьте по факту, см. шаг выше).

## 7. Кладём APK Doxaiz Launcher (prebuilt)

```bash
/path/to/Rust-os-for-android-by-Doxaiz/scripts/fetch-launcher-apk.sh ~/doxaiz-os
```

Скрипт скачивает последний релизный APK из [Doxaiz-android-launcher-/releases](https://github.com/Doxaiz/Doxaiz-android-launcher-/releases) и кладёт его в `vendor/doxaiz/apps/DoxaizLauncher/DoxaizLauncher.apk`. APK в git не коммитится.

## 8. Сборка образа

### 8.1. Cuttlefish (виртуальный телефон для разработки)

```bash
cd ~/doxaiz-os
source build/envsetup.sh
lunch aosp_cf_x86_64_phone-trunk_staging-userdebug   # имя target проверьте: lunch без аргументов перечислит варианты
m -j$(nproc)
```

Если `aosp_cf_x86_64_phone` в вашей ветке не нашёлся — `lunch` покажет список; берите ближайший cuttlefish target (`aosp_cf_x86_64_only_phone-…` в некоторых ветках).

### 8.2. Реальное устройство

Выбор устройства (официальный порт LineageOS, 2 ГБ ОЗУ): [DEVICES.md](DEVICES.md).

```bash
source build/envsetup.sh
lunch lineage_<model>-userdebug       # точное имя: без аргументов после lunch
mka bacon                             # или m -j$(nproc); bacon = OTA zip
```

### 8.3. GSI — образ для ЛЮБОГО устройства с Project Treble

Одна универсальная сборка вместо per-device: `lunch doxaiz_arm64-userdebug` (combo из `vendor/doxaiz/AndroidProducts.mk`; наследует LOS-таргет `gsi_arm64` — ARM64, system-as-root, VNDK enforcement). Артефакты — `out/target/product/generic_arm64/{system.img,vbmeta.img}`. Проверка телефона за 30 секунд, прошивка, обязательный `--disable-verity`, безопасный тест через DSU и честный список ограничений — в [GSI.md](GSI.md).

```bash
scripts/build.sh ~/android/doxaiz doxaiz_arm64-userdebug
# либо вручную: . build/envsetup.sh && lunch doxaiz_arm64-userdebug && m -j$(nproc)
```

Честно: DoxaizOS-GSI в этой песочнице никогда не собирался (нужно ≥ 32–64 ГБ ОЗУ и ≥ 200–400 ГБ диска, см. §0); команды проверены по документации AOSP/LineageOS, а не прогоном. [GSI.md](GSI.md) §6 перечисляет, что GSI не гарантирует (банки, Widevine L1, камера на «капризных» моделях).

## 9. Проверка на Cuttlefish

```bash
# Одноразовая установка Cuttlefish (нужен KVM):
git clone https://github.com/google/android-cuttlefish && cd android-cuttlefish
./tools/buildutils/build_packages.sh
sudo dpkg -i ../cuttlefish-base_*_*64.deb ../cuttlefish-user_*_*64.deb
sudo usermod -aG kvm,cvdnetwork,render $USER && reboot

# После перезагрузки:
launch_cvd --daemon
adb connect 127.0.0.1:6520 && adb devices
```

Либо одной командой: `scripts/cuttlefish-run.sh` (запускает **уже собранный** образ, ждёт `sys.boot_completed=1`, ставит APK, назначает и проверяет HOME, печатает meminfo).

* Адрес ADB по умолчанию — `127.0.0.1:6520` на машине сборщика; переопределение: `DOXAIZ_ADB_TARGET=<serial>`.
* Ожидание загрузки ограничено 300 секундами: `DOXAIZ_BOOT_TIMEOUT=600 scripts/cuttlefish-run.sh /путь/Launcher.apk`. При таймауте скрипт завершается с ошибкой, не пытаясь установить APK.
* Без локального APK допускается пакет, уже встроенный в образ; если `com.doxaiz.launcher` отсутствует или не стал HOME, скрипт завершается с ошибкой вместо запуска произвольного домашнего экрана.
* Offline-тесты оркестрации: `python3 -m unittest discover -s scripts/tests -v`. Они используют подменённые adb/launch_cvd и **не доказывают загрузку Android**. При ошибке скрипт не останавливает Cuttlefish автоматически — экземпляр остаётся доступен для диагностики.

В браузере откройте `https://localhost:8443` — экран виртуального телефона.

## 10. Проверка результата (чек-лист)

```bash
# 1. Роль HOME у Doxaiz Launcher:
adb -s 127.0.0.1:6520 shell cmd package query-intent-activities \
    -a android.intent.action.MAIN -c android.intent.category.HOME
# Ожидаем среди ответов com.doxaiz.launcher/.MainActivity

# 2. Память (цель — docs/ARCHITECTURE.md, §4):
adb -s 127.0.0.1:6520 shell cat /proc/meminfo | grep -E 'MemTotal|MemAvailable'
adb -s 127.0.0.1:6520 shell dumpsys meminfo | head -30

# 3. Версия DoxaizOS:
adb -s 127.0.0.1:6520 shell getprop ro.doxaiz.version     # 0.1.0
adb -s 127.0.0.1:6520 shell getprop ro.config.low_ram     # true

# 4. Лаунчер холодный старт (замер):
adb -s 127.0.0.1:6520 shell am force-stop com.doxaiz.launcher
adb -s 127.0.0.1:6520 shell am start -W -a android.intent.action.MAIN \
    -c android.intent.category.HOME
```

## 11. Флеш на реальное устройство

> Для GSI-образа (любой Treble-телефон) сценарий другой: `fastboot erase system` + `fastboot flash system system.img` + обязательный `--disable-verity --disable-verification` для vbmeta, плюс желательно сначала DSU-тест. Полный рецепт: [GSI.md](GSI.md) §4–5.

```bash
# Разблокировка загрузчика (один раз, стёрет данные!):
adb reboot bootloader
fastboot flashing unlock          # или fastboot oem unlock — зависит от вендора

# Прошивка (пример для типового устройства A/B; точные имена разделов — в
# документации вашего устройства/LOS-порта!):
fastboot flash boot boot.img
fastboot flash system system.img
fastboot flash vendor vendor.img
fastboot -w
fastboot reboot
```

Проще всего: установить [LineageOS Recovery/recovery.img](https://lineageos.org/devices/) для вашей модели и применить собранный OTA-zip через recovery.

## 12. Если что-то сломалось

| Симптом | Куда смотреть |
|---|---|
| `repo sync` рвется | перезапуск команды; `--depth=1`; зеркала `repo init --mirror` |
| `lunch` не находит target | `lunch` без аргументов печатает список; у cuttlefish разные варианты в разных ветках |
| `lunch` не видит `doxaiz_arm64-userdebug` | не применён overlay или нет `vendor/doxaiz/AndroidProducts.mk`; после `apply-overlay.sh` перезапустите `source build/envsetup.sh` |
| GSI не грузится / bootloop на устройстве | проверьте `fastboot --disable-verity --disable-verification flash vbmeta …`; страницы 16K на Android 15+; целостность образа; сначала DSU-тест ([GSI.md](GSI.md)) |
| Не виден `vendor/doxaiz` | apply-overlay.sh копирует в дерево; проверьте путь `vendor/doxaiz/products/doxaiz_base.mk` |
| Сборка падает на DoxaizLauncher | нет `vendor/doxaiz/apps/DoxaizLauncher/DoxaizLauncher.apk` → `scripts/fetch-launcher-apk.sh <дерево>` |
| `inherit-product` не найден | строка добавлена не в тот .mk; `grep -n inherit-product device/...` |
| После удаления Launcher3 нет экрана | не удаляйте его, пока Doxaiz Launcher не HOME (см. LAUNCHER.md) |
| Не хватает ОЗУ при сборке | `export USE_CCACHE=1`, zram на хосте, `-j` меньше числа потоков |

## Проверка оркестратора сборки без Android-дерева

```bash
# Из корня репозитория, без скачивания AOSP:
python3 -m unittest discover -s scripts/tests -v
```

`test_build.py` проверяет 6 сценариев `scripts/build.sh`: относительный путь с пробелами, абсолютный путь, существующий `.repo`, ошибка sync, ошибка lunch, ошибка m. Подменяются repo, сетевые команды и функции envsetup; реальное копирование overlay и проверка mock APK выполняются штатными helper-скриптами. Это проверка порядка действий и распространения ошибок, **не сборка прошивки**.

Путь дерева приводится к абсолютному до перехода в него. Локальный манифест копируется **после repo init, но до первого repo sync**: один sync вместо двух, без предварительного скачивания исключённых проектов. Удаления всё ещё требуют проверки полной сборкой.

Примеры, сверенные через GitHub API 2026-11-23:

* [Документация repo: Local Manifests](https://github.com/aosp-mirror/tools_repo/blob/main/docs/manifest-format.md) — расположение `.repo/local_manifests/*.xml` и расширение основного манифеста.
* [LineageOS getting started (lineage-23.0)](https://github.com/LineageOS/android/blob/lineage-23.0/README.mkdn) — разделение init и sync. Пример использован для понимания порядка, не как доказательство совместимости нашей ветки или модели телефона.

### Защита от случайной сборки обычного Android

После `lunch` и **до** `m` скрипт `build.sh` запрашивает через `build/soong/soong_ui.bash --dumpvar-mode` вычисленные `PRODUCT_PACKAGES` и `PRODUCT_PROPERTY_OVERRIDES`. Требуются точное имя модуля `DoxaizLauncher`, `ro.config.low_ram=true` и непустая `ro.doxaiz.version`. При отсутствии или ошибке dumpvar сборка останавливается. Одного копирования overlay в `vendor/doxaiz` недостаточно — выбранный продукт должен наследовать `doxaiz_base.mk`.

Механика dumpvar сверена с [LineageOS envsetup.sh (lineage-23.0)](https://github.com/LineageOS/android_build/blob/lineage-23.0/envsetup.sh), `_get_build_var_cached`, через GitHub API 2026-11-23. В современных ветках публичный `get_build_var` может быть отдельной командой, а не shell-функцией; обёртка использует непосредственно Soong UI.

Проверка конфигурации не доказывает, что APK попал в конечный образ, свойства не были переопределены позднее или HOME работает. После сборки обязательны проверка артефактов и запуск по чеклисту. Дополнительные offline-сценарии проверяют отсутствие модуля (включая похожее имя), свойств и ошибку dumpvar с остановкой до `m`.
