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

Скрипт копирует `overlay/vendor/doxaiz` → `vendor/doxaiz`.

Для Cuttlefish теперь зарегистрирован собственный продукт `doxaiz_cf_x86_64_phone`: он уже наследует upstream и `doxaiz_base.mk`; вручную менять файлы Google не надо. Продукт ещё не прошёл настоящий `lunch/m`.

Для per-device продукта добавьте в product make-файл устройства:

```makefile
$(call inherit-product, vendor/doxaiz/products/doxaiz_base.mk)
```

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
lunch doxaiz_cf_x86_64_phone-trunk_staging-userdebug  # кандидат, ещё не собран
m -j$(nproc)
```

Продукт наследует проверенный исходник AOSP android-17.0.0_r1 `device/google/cuttlefish/vsoc_x86_64_only/phone/aosp_cf.mk`, сохраняя `PRODUCT_DEVICE=vsoc_x86_64_only`. У upstream включены игнорирование Android.mk и фиксированный Soong system image: просто добавить PRODUCT_PACKAGES недостаточно для нашего Make-prebuilt. Обёртка явно возвращает mixed Make/Soong сборку и отключает фиксированный system image. Проверены только наследование/переменные на GNU Make-фикстуре, не работоспособность Android-сборки. Release config `trunk_staging` взят из upstream AndroidProducts.mk; его совместимость с новым продуктом ещё надо проверить настоящим lunch.

Перед сборкой `scripts/build.sh` для этого таргета применяет `scripts/apply-home-fallback-patch.sh`: HOME priority штатного Launcher3/Quickstep становится -1; неизменённый Doxaiz APK имеет 0. Сам Launcher3 и recents-сервис остаются. Helper проверен на точных исходниках LOS Launcher3 `3e0e4f1955992788768547ae2c4115537bc957a6`, не на настоящей компиляции. Если собираете вручную без build.sh, отдельно выполните `bash /path/to/repo/scripts/apply-home-fallback-patch.sh ~/doxaiz-os` перед lunch/m. При upstream drift helper отказывает; не обходите отказ без ревью. История отвергнутого XML-варианта и границы проверки — [LAUNCHER.md](LAUNCHER.md).

Не заменяйте неработающий doxaiz target ближайшим stock target: так можно незаметно собрать чужую ОС без наших изменений.

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

Для разработки лаунчера, **не для приёмки прошивки**, можно воспользоваться `scripts/cuttlefish-run.sh` (запускает **уже собранный** образ, ждёт `sys.boot_completed=1`, ставит APK, назначает и проверяет HOME, печатает meminfo).

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


## 12. Доставка собственной сборки на бесплатный тест-хост

Для Cuttlefish target `doxaiz_cf_x86_64_phone-*` `build.sh` теперь запускает явные цели:

```bash
DIST_DIR="$EVIDENCE/dist" m -j"$(nproc)" dist dist_files target-files-package updatepackage hosttar
```

`EVIDENCE` — новый уникальный каталог текущей сборки, dist изначально пуст. `updatepackage` создаёт image ZIP из target-files; `target-files-package` экспортирует target-files; Cuttlefish `hosttar` строит host package, а `dist_files` явно включает его dist-правило. После exit 0 требуются ровно один `doxaiz_cf_x86_64_phone-img*.zip`, один `doxaiz_cf_x86_64_phone-target_files*.zip` и обычный файл `cvd-host_package.tar.gz`. Отсутствие, symlink или неоднозначный набор — отказ, без выбора «самого нового» старого файла. Далее штатный `firmware-bundle.py export` проверяет target-files identity и создаёт `$EVIDENCE/bundle` с хешами и manifest. Содержимое dist и source evidence нужно сохранять вместе; target-files не копируется в bundle, но остаётся в dist.

Цели сверены с [build/core/Makefile](https://github.com/LineageOS/android_build/blob/90d006387398ae6899145e6531a304500cfa0f70/core/Makefile) и [Cuttlefish cvd-host-package.go android-17.0.0_r1](https://github.com/aosp-mirror-neo/device_google_cuttlefish/blob/android-17.0.0_r1/build/cvd-host-package.go). **Новая полная команда не выполнена на Android-дереве**: проверена только fake-m оркестрация. Соответствие конкретной Soong/Make интеграции ещё требует настоящей сборки. Non-Cuttlefish targets сохраняют прежний обычный `m`, без попыток упаковать их как Cuttlefish.

Ниже сохранён ручной export для уже имеющихся артефактов одной доверенной сборки. Он ничего не компилирует и не подменяет отсутствующие артефакты stock-образами.

В Android-дереве сохраните pinning после завершённого sync:

```bash
repo manifest -r -o /absolute/path/repo-manifest.xml
# Manifest не включает локальные source patches! Сохранить отдельно:
repo diff > /absolute/path/source-diff.patch
sha256sum /absolute/path/source-diff.patch
```

`scripts/build.sh` теперь автоматически создаёт новый каталог `doxaiz-build-evidence.XXXXXXXX` в Android-дереве **после** overlay/source patch/APK и **до** lunch/компиляции. В него попадают `repo-manifest.xml` (`repo manifest -r`, все project revision проверяются как SHA-1), `source-diff.patch` (`repo diff`), `source-evidence.json` (lunch, commit/status Doxaiz checkout, SHA-256 manifest/diff/APK) и `result.json` (exit code и последняя фаза). Ошибка manifest/diff/валидации останавливает путь до `m`; ошибка lunch/product gates/m не записывается как успешная сборка. Каталог находится вне `out/`, но сохраняйте его отдельно перед удалением Android-дерева.

**Ограничения:** `repo diff` не архивирует untracked/ignored файлы и не включает содержимое целого vendor overlay; manifest не фиксирует произвольные локальные APK/изменения. Commit/status checkout + APK hash — описание происхождения, не полная герметичная сборка и не подпись. Сохранять исходный Doxaiz checkout, все дополнительные untracked inputs и полный build log отдельно. Статус `build-command-completed` означает лишь exit 0 команды `m`: наличие требуемых dist-артефактов, boot и CTS проверяются отдельно.

Source diff и вывод SHA-256 apply-home-fallback-patch.sh сохранять рядом с полным build log. Текущий bundle автоматически не включает source-diff.patch: без отдельного сохранения локальные изменения Launcher3 не воспроизводятся по одному repo manifest -r. Хеш DoxaizOS commit фиксирует содержимое patch/helper, но не все сторонние изменения Android-дерева.

Из репозитория DoxaizOS экспортируйте комплект (пути placeholders заменить реальными):

```bash
python3 scripts/firmware-bundle.py export \
  --images /absolute/build/images.zip \
  --host-tools /absolute/build/cvd-host_package.tar.gz \
  --target-files /absolute/build/target-files.zip \
  --repo-manifest /absolute/path/repo-manifest.xml \
  --source-commit "$(git rev-parse HEAD)" \
  --output reports/own-cuttlefish-bundle
```

Экспорт читает ожидаемые fingerprint/version/low_ram из build.prop внутри target-files, проверяет наличие APK-entries DoxaizLauncher и pinned project revisions. Копирует images, tools, manifest в новый каталог, считает SHA-256 потоково. Target-files не копируется второй раз, но его SHA-256 записывается. Имя APK-entry — лишь проверка состава, **не** анализ APK/подписи или проверка HOME.

Распечатанный SHA-256 `bundle.json` сохраните через доверенный канал сборщика. На получателе:

```bash
python3 scripts/firmware-bundle.py verify \
  --bundle reports/own-cuttlefish-bundle \
  --metadata-sha256 SHA256_FROM_TRUSTED_BUILD_CHANNEL
```

Отказ при повреждении, подмене metadata, symlink-артефакте, незакреплённом manifest, отсутствии версии/fingerprint/low_ram/Launcher-entry или перезаписи output. Содержимое архивов не извлекается и не исполняется. Export/verify — **контроль доставки, не boot и не подлинность сборщика**: они не доказывают соответствие images ↔ target-files ↔ tools, хеш commit лишь фиксирует заявленное происхождение. Согласованность обеспечивает доверенная сборочная процедура. Реальных артефактов DoxaizOS пока нет; протестированы синтетические ZIP.

Добавлены безопасная распаковка и отдельный CI-путь собственного bundle (раздел ниже). Эталонный workflow по-прежнему запускает Google AOSP, а не DoxaizOS; он также может проверять отказ stock-образу через новую оркестрацию — [FIRMWARE-LAB.md](FIRMWARE-LAB.md).


### 12.1. Подготовленный путь запуска собственного комплекта

`unpack-firmware.py` сначала проверяет metadata SHA и хеши комплекта, затем пути и типы всех ZIP/TAR entries. Отказывает абсолютным путям, `..`, ZIP-symlink, hardlink/FIFO/device, коллизиям, записи под ссылкой, отсутствию исполняемых bin/launch_cvd и bin/stop_cvd (включая допустимые ссылки на обычные файлы строго внутри распакованного дерева). TAR ownership/setuid не переносится; ссылки создаются последними. По умолчанию предел распакованных данных 30 GiB, плюс проверка свободного диска. Это ограничение распаковки, не бюджет runtime userdata/памяти. Из соображений безопасности TAR-ссылки с `..` тоже отвергаются, даже если конкретная ссылка могла бы остаться внутри дерева; совместимость с собственным реальным host package ещё предстоит проверить.

На **одноразовом уже подготовленном KVM-хосте**:

```bash
bash scripts/boot-firmware-bundle.sh \
  reports/own-cuttlefish-bundle SHA256_FROM_TRUSTED_BUILD_CHANNEL \
  reports/own-boot-001
```

Путь проверяет /dev/kvm, отсутствие старого ADB TCP listener/онлайн-устройства на 127.0.0.1:6520, распаковывает в новый приватный каталог, запускает только инструменты проверенного комплекта (2 CPU, 2048 МБ, SwiftShader). После загрузки вызывает read-only check-firmware.py с ожидаемой identity из проверенного bundle. **Не устанавливает APK, не меняет HOME или ro-свойства**. Гость должен пройти gates в состоянии, полученном при сборке. launch ограничен 900 с, дополнительное ожидание Android — 300 с. В EXIT trap собирает logcat/хвосты launcher/kernel logs и останавливает экземпляр; ошибка stop не превращается в PASS. Теперь после первого baseline запускается check-os-lifecycle.py: запись случайного маркера только в /data/local/tmp, sync, полный adb reboot, новый kernel boot UUID + увеличившийся boot_count + sys.boot_completed, проверка сохранности маркера, fingerprint continuity, SELinux и служб. Затем **повторно** запускается check-firmware.py с той же независимой expected version/fingerprint из проверенного bundle. Смена версии, HOME, low-RAM или SELinux после reboot не исправляется командами: это отказ. После проверки маркер удаляется; ошибка удаления также не считается PASS. Собственный образ этой новой последовательностью ещё не проверен.

**Исполнение host tools — исполнение нативного кода сборщика.** Проверка хешей и безопасные пути не делают вредоносную сборку безопасной. Не использовать непроверенные чужие release-assets, постоянный runner с секретами или персональный телефон. Имя APK-entry/ro-свойства также не являются криптографической аттестацией.

### 12.1.1. Отдельная проверка жизненного цикла одноразовой VM

**Команда изменяет userdata тестовой VM и перезагружает её**, не является read-only сбором диагностики:

```bash
python3 scripts/check-os-lifecycle.py \
  --serial 127.0.0.1:6520 \
  --output reports/cvd-lifecycle-001 \
  --allow-disposable-reboot
```

Без явного флага, с другим serial, не-Cuttlefish ro.hardware или существующим каталогом отчёта — отказ. ro.hardware — защита от случайной ошибки, не криптографическая аттестация. Применять только к своей одноразовой Cuttlefish, не к телефону/постоянной VM с данными. Marker имеет случайные имя и содержимое, не перезаписывает фиксированный файл. Перед reboot требуется корректный boot UUID, завершённая загрузка, SELinux Enforcing и основные Binder-службы. Команды ADB ограничены 20 с (cleanup 5 с), общее ожидание повторной загрузки по monotonic clock — 300 с, --boot-timeout допускает 1..900 с. Реконнекты не сбрасывают deadline. Изменение одного boot_count без нового kernel boot UUID не проходит.

В новом каталоге 0700 сохраняются result.json, stdout/stderr и точные команды. /proc/meminfo, /proc/swaps, /proc/pressure/memory, ZRAM comp_algorithm/mm_stat/disksize читаются до/после reboot как **необязательная сырая диагностика**. Недоступность фиксируется явно; наличие файла не доказывает активный swap, соответствие 50%/75%, алгоритм zstd, экономию памяти или отсутствие троттлинга. Это не нагрузочный тест.

Наблюдаемый fingerprint в standalone lifecycle проверяет лишь неизменность через reboot, **не происхождение образа**. В own-bundle pipeline его дополняют две независимые проверки firmware identity по metadata сборщика. reference-os-test.sh теперь использует тот же lifecycle-код, но отчёт эталона явно помечен NOT DoxaizOS.

### 12.2. Бесплатный CI для своего образа

`.github/workflows/firmware-own.yml` получает четыре release-assets **этого же GitHub-репозитория**: bundle.json, images.zip, cvd-host_package.tar.gz, repo-manifest.xml. Загруженные файлы проверяются до подготовки хоста; далее запускается сценарий выше. Публикация release-assets пока не автоматизирована и не выполнялась: реального своего комплекта нет. Не надо создавать фиктивный release для зелёного CI.

После появления доверенной сборки можно добавить `.github/firmware-lab-request.json` в текущую ветку:

```json
{
  "release_tag": "ACTUAL_OWN_BUILD_RELEASE_TAG",
  "metadata_sha256": "ACTUAL_64_HEX_SHA256_FROM_TRUSTED_BUILDER"
}
```

Это шаблон, не готовая заявка: оба значения заменить фактическими. Commit/push файла запускает job на standard public ubuntu-24.04 (не larger, не self-hosted). Repo должен оставаться public; GH_TOKEN только contents:read, внешние репозитории не принимаются. Inputs не интерполируются как shell-код. Workflow_dispatch тоже описан, но GitHub обычно показывает ручной запуск только после появления workflow в default branch: **не требуется сливать PR ради этого**, push-заявка работает в текущей arena-ветке.

Если заявки нет, own-os **SKIPPED**, не firmware PASS. Отдельный инфраструктурный job проверяет только установку cuttlefish-base, сеть и KVM. Установщик отказывает вне github-hosted Ubuntu 24.04, меняет группы/KVM/AppArmor исключительно внутри одноразовой VM. APT-зависимости пока не зафиксированы по версии, репозиторий доверяется ключу Google. Автоматическая регистрация/покупка облачных машин не используется.

В artifacts попадают только диагностические файлы на 7 дней, **не** огромные images/tools. Они могут содержать сведения гостевой системы: для публичного CI использовать только очищенные тестовые userdata и сборки без секретов.
