# Сборка DoxaizOS

DoxaizOS — это «slim-профиль» поверх LineageOS/AOSP: свой overlay, свой рабочий стол, low-RAM свойства. Поэтому сборка = обычная сборка LineageOS 24.0 + один overlay.

> Где собирать: только на Linux x86_64-машине сборщика (рекомендуем ≥ 16 ГБ ОЗУ, ≥ 250 ГБ SSD, ≥ 8 ядер). В браузерной песочнице и в обычном CI полную сборку AOSP не прогнать (нужно 60–90 ГБ синхронизации и часы компиляции) — CI в этом репозитории проверяет всё, что можно проверить дёшево (Rust-тесты, ссылки, синтаксис, структуру overlay).

## 0. Проверка окружения

```bash
nproc                       # ≥ 8 желательно
free -g                     # ≥ 12–16 ГБ
df -h .                     # ≥ 250 ГБ свободно
python3 --version           # 3.8+
git --version
```

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

```bash
source build/envsetup.sh
lunch lineage_<model>-userdebug       # точное имя: без аргументов после lunch
mka bacon                             # или m -j$(nproc); bacon = OTA zip
```

## 9. Проверка на Cuttlefish

```bash
# Одноразовая установка Cuttlefish (нужен KVM):
git clone https://github.com/google/android-cuttlefish && cd android-cuttlefish
./tools/buildutils/build_packages.sh
sudo dpkg -i ../cuttlefish-base_*_*64.deb ../cuttlefish-user_*_*64.deb
sudo usermod -aG kvm,cvdnetwork,render $USER && reboot

# После перезагрузки:
launch_cvd --daemon
adb connect 0.0.0.0:6520 && adb devices
```

Либо одной командой: `scripts/cuttlefish-run.sh` (запускает образ, ставит APK, назначает HOME, печатает meminfo).

В браузере откройте `https://localhost:8443` — экран виртуального телефона.

## 10. Проверка результата (чек-лист)

```bash
# 1. Роль HOME у Doxaiz Launcher:
adb -s 0.0.0.0:6520 shell cmd package query-intent-activities \
    -a android.intent.action.MAIN -c android.intent.category.HOME
# Ожидаем среди ответов com.doxaiz.launcher/.MainActivity

# 2. Память (цель — docs/ARCHITECTURE.md, §4):
adb -s 0.0.0.0:6520 shell cat /proc/meminfo | grep -E 'MemTotal|MemAvailable'
adb -s 0.0.0.0:6520 shell dumpsys meminfo | head -30

# 3. Версия DoxaizOS:
adb -s 0.0.0.0:6520 shell getprop ro.doxaiz.version     # 0.1.0
adb -s 0.0.0.0:6520 shell getprop ro.config.low_ram     # true

# 4. Лаунчер холодный старт (замер):
adb -s 0.0.0.0:6520 shell am force-stop com.doxaiz.launcher
adb -s 0.0.0.0:6520 shell am start -W -a android.intent.action.MAIN \
    -c android.intent.category.HOME
```

## 11. Флеш на реальное устройство

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
| Не виден `vendor/doxaiz` | apply-overlay.sh копирует в дерево; проверьте путь `vendor/doxaiz/products/doxaiz_base.mk` |
| Сборка падает на DoxaizLauncher | нет `vendor/doxaiz/apps/DoxaizLauncher/DoxaizLauncher.apk` → `scripts/fetch-launcher-apk.sh <дерево>` |
| `inherit-product` не найден | строка добавлена не в тот .mk; `grep -n inherit-product device/...` |
| После удаления Launcher3 нет экрана | не удаляйте его, пока Doxaiz Launcher не HOME (см. LAUNCHER.md) |
| Не хватает ОЗУ при сборке | `export USE_CCACHE=1`, zram на хосте, `-j` меньше числа потоков |
