# DoxaizOS как GSI: переносимость и ограничения Project Treble

> GSI — переносимый системный образ, но **не один образ для любого телефона**. Требуется совпадение ABI (arm64 и arm32-binder64/A64 не взаимозаменяемы), совместимый vendor/VNDK, схема разделов и доступный способ загрузки. Treble сам по себе не гарантирует совместимость; DSU доступен не везде. Для выбранного Redmi 9A см. [REDMI-9A.md](REDMI-9A.md): текущий `doxaiz_arm64` не считается подходящим.

> Честность: команды ниже сверены с документацией AOSP/LineageOS и исходниками LOS lineage-24.0 (`device/generic/common/gsi_arm64.mk`), но **сборка DoxaizOS-GSI ни разу не выполнялась** — для этого нужен ПК с ≥ 32–64 ГБ ОЗУ и ≥ 200–400 ГБ диска ([BUILD.md](BUILD.md) §0). Всё, что не промерено на железе, помечено как цель, а не факт.

## 1. Что такое GSI и почему это «любой телефон»

* GSI — «голый» системный образ Android (чисто AOSP), **не привязанный к железу**. Ядро и vendor-партиция берутся у самого телефона; GSI заменяет только `/system`.
* Project Treble (Android 8+, обязателен для новых устройств) разделил платформу и вендорские драйверы через **VNDK** и стабильные HAL-интерфейсы — поэтому один и тот же system.img грузится на тысячах устройств без пересборки.
* GSI — то, как Google тестирует совместимость на реальных устройствах (и то, чем пользуется всё сообщество кастомных прошивок: TrebleDroid/phhusson, AndyYan и др. публикуют именно GSI). [34][41]

## 2. Проверка телефона за 30 секунд

```bash
# 1. Treble включён?
adb shell getprop ro.treble.enabled          # ожидаем: true
# 2. Архитектура (нужна ARM64 GSI для 64-битных устройств)
adb shell getprop ro.product.cpu.abi         # arm64-v8a — стандарт
# 3. Динамические разделы (для DSU без прошивки)
adb shell getprop ro.boot.dynamic_partitions # true
# 4. Страничный размер (Android 15+ бывают 16K-страницы!)
adb shell getconf PAGE_SIZE                  # 4096 или 16384
# 5. Разблокирован ли загрузчик (обязателен!)
adb reboot bootloader; fastboot oem device-info | head   # Unlocked: true
```

| Ответ | Значение |
|---|---|
| `ro.treble.enabled=true` | ✅ GSI годится |
| `ro.treble.enabled` отсутствует/false | ❌ Только per-device порт ([DEVICES.md](DEVICES.md)) |
| `Unlocked: false` | ❌ GSI (не подписанная Google) не загрузится; unlock стирает данные |
| `PAGE_SIZE=16384` | ⚠️ нужна 16K-страничная GSI-сборка (Android 15+); либо 4K-прошивка, если вендор 4K |

## 3. Сборка DoxaizOS-GSI

GSI собирается из **того же дерева** LineageOS/AOSP (раздел [BUILD.md](BUILD.md); в манифесте LineageOS есть `device/generic/arm64` из AOSP).

### Путь B — GSI из дерева LineageOS 24.0 (основной для DoxaizOS)

В манифесте lineage-24.0 проект `device/generic/arm64` берётся из AOSP, а проект `device/generic/common` (`LineageOS/android_device_generic_common`) содержит **готовые GSI-продукты**, включая `gsi_arm64` (ARM64, 64-битный binder, system-as-root, VNDK enforcement) — его и наследует наш оверлей `overlay/vendor/doxaiz/products/doxaiz_gsi.mk` (+ `doxaiz_base.mk`). Официальная инструкция AOSP для GSI — `lunch gsi_arm64-userdebug`, артефакт `out/target/product/generic_arm64/system.img`. [43] Регистрация — через `overlay/vendor/doxaiz/AndroidProducts.mk`, поэтому после `apply-overlay.sh` в списке lunch появляется `doxaiz_arm64-userdebug`:

```bash
scripts/build.sh ~/android/doxaiz doxaiz_arm64-userdebug     # sync + overlay + envsetup + lunch + m
# либо вручную:
. build/envsetup.sh
lunch doxaiz_arm64-userdebug     # combo из vendor/doxaiz/AndroidProducts.mk
m -j$(nproc)                     # артефакты: out/target/product/generic_arm64/{system.img,vbmeta.img}
```

Так собирает и сообщество (сборки AndyYan `…-gsi_arm64_vN.img.gz` на LOS/AOSP — рабочие). Внутри `gsi_arm64.mk`: `core_64_bit` + `generic_system` + `gsi_system_ext` (SystemUI, Settings, Provision, StorageManager, CarrierConfig…) + `gsi_product` + `gsi_release` + `MODULE_BUILD_FROM_SOURCE=true` + `PRODUCT_SOONG_DEFINED_SYSTEM_IMAGE=android_gsi`. BoardConfig ищется как `device/*/generic_arm64/BoardConfig.mk` (найден AOSP-проект `device/generic/arm64`); поэтому `PRODUCT_DEVICE=generic_arm64` **менять нельзя**. [41][42]

### Путь A — чистая AOSP-база

Если нужно без LOS (например, для отладки чистого AOSP):

```bash
repo init -u https://android.googlesource.com/platform/manifest -b android-17.0.0_r1 --depth=1
repo sync -c --no-tags --optimized-fetch --prune -j$(nproc)
scripts/apply-overlay.sh "$PWD"   # overlay ляжет в vendor/doxaiz (продукты: doxaiz_gsi.mk)
source build/envsetup.sh
lunch aosp_arm64-userdebug        # точный combo покажет `lunch`; на Android 17 бывает
                                  # вид release-config, напр. aosp_arm64-aosp_current-userdebug
m -j$(nproc)                      # или: m systemimage vbmetaimage
```

В чистом AOSP-дереве `doxaiz_gsi.mk` наследует `device/generic/common/gsi_arm64.mk` — а этого проекта в чистом AOSP-манифесте **нет** (это LOS-проект). Для AOSP-базы замените первую строку `inherit-product` в `doxaiz_gsi.mk` на `device/generic/arm64/aosp_arm64.mk` (GSI-продукт AOSP) и соберите `lunch aosp_arm64-userdebug`, либо просто соберите штатный GSI и влейте Doxaiz-пакеты в `generic_system.mk`-совместимый продукт. Деревья LOS и AOSP различаются — не смешивайте их в одной сборке. [34][35]

### Артефакты и официальный базлайн

```
out/target/product/generic_arm64/system.img
out/target/product/generic_arm64/vbmeta.img
```

Официальные GSI от Google (для сравнения и базлайнового тестирования) есть в двух вариантах — **vanilla** и **+GMS**, ARM64 и x86_64: [developer.android.com/topic/generic-system-image/releases](https://developer.android.com/topic/generic-system-image/releases). DoxaizOS-GSI — vanilla по политике («ноль Google»). [34][35]

### Размер и место

* DoxaizOS-GSI весит ориентировочно **~900 МБ (сжатый) / 2,2–2,6 ГБ (сырой system.img)** — впритык для старых Go-устройств с `/system` ~2 ГБ: проверьте свободное место и, при нужде, увеличивайте через repartitioning (продвинутый сценарий, не для первой установки).
* Проверка до прошивки: `du -h system.img` и сравнение с размером `/system` (в stock-прошивке `df /system` до перепрошивки).

## 4. Прошивка GSI на реальное устройство

> Разблокировка загрузчика сотрёт все данные. Сделайте бэкап.

```bash
# 0. Разблокировка (один раз): настройки → «Для разработчиков» → разблокировка OEM
adb reboot bootloader
fastboot flashing unlock          # или fastboot oem unlock — по вендору; подтвердить на экране

# 1. Отключить verity для своего образа (обязательно!):
fastboot --disable-verity --disable-verification flash vbmeta vbmeta.img

# 2. Обязательно для динамических разделов (Android 10+):
fastboot reboot fastboot          # перейти в fastbootd (userspace fastboot)
#    --- на не-динамических разделах (старые A-only) пропустите и используйте обычный fastboot ---

# 3. Залить образ:
fastboot erase system             # динамические: стирает логический раздел
fastboot flash system system.img

# 4. Стереть данные и перезагрузиться:
fastboot -w
fastboot reboot
```

Проверка после первой загрузки:

```bash
adb shell getprop ro.doxaiz.version     # 0.1.0
adb shell getprop ro.build.fingerprint  # …generic_arm64/…
adb shell pm list packages | grep doxaiz || true
adb shell dumpsys package com.doxaiz.launcher | grep versionName
```

**Откат:** прошить stock-образ своего телефона (раздел `/system` заменим на любой GSI/другую прошивку); данные при `-w` стираются — откат без потерь данных возможен только через бэкап (Swift Backup и т.п.).

## 5. Тест БЕЗ прошивки: Dynamic System Updates (DSU)

Самый безопасный способ «пощупать» DoxaizOS на конкретной модели (Android 10+, динамические разделы, ≥ 40 % свободного места, разблокированный загрузчик):

1. Поставить [DSU Sideloader](https://f-droid.org/packages/vegabobo.dsusideloader/) (F-Droid, `vegabobo.dsusideloader`).
2. Положить `system.img.gz` на телефон; размер образа — кратный 512 байт.
3. В приложении выбрать образ и userdata ≥ 8 ГБ, подтвердить — Android сам скачает/создаст динамическую систему во `/data/gsi`, оригинальная прошивка **останется нетронутой**.
4. Перезагрузка → в шторке появится «Dynamic System» → телефон грузит DoxaizOS рядом со старой системой. Вернуться можно любым ребутом без `fastboot`.

Либо вручную через adb:

```bash
gzip -c system.img > system.img.gz
adb push system.img.gz /sdcard/Download/
adb shell am start-activity \
    -n com.android.dynsystem/com.android.dynsystem.VerificationActivity \
    -a android.os.image.action.START_INSTALL \
    -d file:///sdcard/Download/system.img.gz \
    --el KEY_SYSTEM_SIZE $(stat -c%s system.img) \
    --el KEY_USERDATA_SIZE 8589934592
```

DSU — лучший инструмент проверки совместимости: если GSI не грузится, устройство просто возвращается в stock. [36][37][38][39][40]

## 6. Что GSI НЕ делает (честный список)

| Пункт | Почему | Что делать |
|---|---|---|
| Телефоны без Treble (Android < 8) | нет VNDK-разделения | per-device порт ([DEVICES.md](DEVICES.md)) |
| Некоторые Android Go (2 ГБ) без VNDK-библиотек | GSI ожидает полный VNDK у вендора | искать vndklite-сборки (TrebleDroid/phhusson, включает phh-патчи для Go); тестировать через DSU [41] |
| Verified boot (AVB) для своего GSI | свой vbmeta не подписан вендорским ключом | отключить verity при прошивке (осознанно; [SECURITY.md](SECURITY.md)) или ждать release-ключи вендора |
| Банковские приложения / Play Integrity | кастомная прошивка = SafetyNet/Integrity fail | не ставить DoxaizOS на «основной» телефон с банками или включать Magisk/PlayIntegrityFix (вне скоупа) |
| DRM (Widevine L1 → L3) | GSI не сертифицирован вендором | HD-видео стриминг может деградировать, при DSU-тесте видно сразу |
| Камера/BT/дактилоскоп на «капризных» моделях | vendor HAL-баги | DSU-тест на целевой модели до прошивки; известные проблемы GSI трекера: Bluetooth на некоторых, dual-SIM на Qualcomm single-SIM [37] |
| 16K страницы на Android 15+ | несовместимая сборка не грузится | брать 4K GSI или собирать 16K-вариант под своё железо |
| Gemini/GMS | сознательно нет в DoxaizOS | F-Droid/APK |

## 7. Матрица покрытия DoxaizOS (итого)

| Путь | Покрытие | Когда |
|---|---|---|
| **GSI (этот док)** | все Treble-устройства ARM64 (2017+) — тысячи моделей | основная массовая поставка, тесты на любой технике вне матрицы LOS |
| Per-device LOS port | сотни протестированных моделей ([DEVICES.md](DEVICES.md)) | «идеальное» поведение на конкретной модели |
| Cuttlefish | виртуальная машина (CI/ПК) | разработка |
| DSU | временное включение на своём телефоне | «попробовать перед прошивкой» |

**Итог:** «одна прошивка на любой телефон» = GSI + обязательный разблокированный загрузчик + DSU для безопасного теста. Это максимум универсальности во всей индустрии Android — большего не даёт никто (ни LineageOS, ни Google, ни Xiaomi).

## 8. Источники

34. Generic System Image releases — официальные GSI Android 17 (vanilla и +GMS, ARM64/x86_64, flash.android.com) — https://developer.android.com/topic/generic-system-image/releases
35. Let's clone & build AOSP Android 17 (GSI path: lunch aosp_arm64-cp2a-userdebug; erase system_a/b; vbmeta --disable-verity) — https://goyaljai.medium.com/lets-clone-build-aosp-android-17-659554404340
36. Build & Flash custom AOSP GSI on Pixel / Android 16 (vbmeta disable-verity; fastbootd; `m systemimage vbmetaimage`) — https://proandroiddev.com/building-flashing-a-custom-aosp-gsi-on-pixel-arm64-android-16-1313b4211c53
37. XDA: Build AOSP GSI from source and flash it with DSU (gzip system.img, adb push, START_INSTALL intent; «gsi_arm64 is a subset of aosp_arm64») — https://xdaforums.com/t/build-aosp-gsi-from-source-and-flash-it-with-dsu.4749904/
38. DSU Sideloader (F-Droid; Android 10+; unlocked bootloader; dynamic partitions; gsid требует ≥ 40 % свободного места) — https://f-droid.org/packages/vegabobo.dsusideloader/
39. Dynamic System Updates deep dive (Dynamic Partitions, /data/gsi, START_INSTALL, KEY_SYSTEM_SIZE/USERDATA_SIZE; sandbox) — https://archive.ph/FsuMj
40. LG/XDA: Android 11 DSU Loader (родной DSU в Developer Options; bootloader должен быть unlocked for unsigned GSI) — https://lg-g4-xda.blogspot.com/2020/03/android-11s-dsu-loader-makes-it-easier.html
41. TrebleDroid GSI list (LineageOS 24.0 GSI by Aizner/AndyYan, Android 17; ландшафт альтернатив) — https://github.com/TrebleDroid/treble_experimentations/wiki/Generic-System-Image-%28GSI%29-list
42. AndyYan GSI builds (aosp-pure-userdebug/lineage-*-gsi_arm64, android-17.0.0_r1, ~900 МБ .img.gz) — https://sourceforge.net/projects/andyyan-gsi/files/aosp-pure-userdebug/
43. AOSP — Generic system images (официальная инструкция: GSI-ветки/таргеты, `lunch gsi_arm64-userdebug`, артефакт `out/target/product/generic_arm64/system.img`) — https://source.android.com/docs/core/tests/vts/gsi
44. TrebleDroid — treble_experimentations (phhusson-патчи + GSI README: vndklite-сборки для Go-устройств; GSI как «system.img поверх vendor») — https://github.com/TrebleDroid/treble_experimentations
