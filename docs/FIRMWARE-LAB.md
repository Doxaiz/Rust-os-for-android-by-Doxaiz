# Где проверять именно ОС: лаборатория DoxaizOS

## Вывод исследования

Выбранный путь: **собственный Cuttlefish-образ DoxaizOS + Linux-хост с KVM**. Сборка и запуск — разные задачи. Компилировать можно на большой машине, запускать полученный комплект — на другом, меньшем хосте с виртуализацией. Не требуется 64 ГБ ОЗУ лишь для каждой проверки загрузки: это опубликованное требование современной AOSP-сборки, не универсальный минимум запуска Cuttlefish.

Аренда, платные runner и облачные ресурсы в этой работе не создавались. Образ DoxaizOS не собран; бесплатный эталонный Cuttlefish-стенд ниже уже проверен, но собственная ОС на нём ещё не запускалась. Успех ранее выполненного Launcher-теста не считается успехом ОС.

## Сопоставление вариантов

| Вариант | Собственный образ ОС | Сборка | Что ограничивает |
|---|---|---|---|
| Cuttlefish на своём Linux / выделенном сервере | Да, согласованный комплект Cuttlefish images + host package | На этом или другом хосте | Нужны KVM, права/группы, совместимые host tools и образы; не MediaTek-эмулятор |
| Cuttlefish в Compute Engine через acloud | Да, `--local-image` передаёт собственную сборку | Отдельно или на подходящей VM | Учётная запись, billing, квота, nested virtualization, сеть; доступность по региону/аккаунту надо проверять |
| Self-hosted GitHub runner на таком сервере | Да, это способ оркестрации, а не другой эмулятор | Да при достаточных ресурсах | Сервер оплачивается/предоставляется отдельно; нельзя исполнять недоверенные PR на постоянной машине с секретами |
| GitHub larger Linux runner | Подходит как кандидат для сборки, запуск зависит от KVM конкретной конфигурации | Опубликован вариант 16 CPU / 64 GB / 600 GB | Платный даже для public repo, зависит от плана/прав; label берётся из конфигурации runner, не угадывается |
| Стандартный GitHub runner + готовый Cuttlefish-комплект | Кандидат для boot-smoke при достаточном диске и доступном KVM | Полную современную AOSP-сборку не закладываем | Сначала нужен наш образ; штатный образ Google проверит только лабораторию |
| Наш существующий Android Emulator API 29 job | Сейчас только штатный system image + APK | Не собирает DoxaizOS | Его PASS не подтверждает собственную прошивку |
| Genymotion | Исключён для этой задачи | — | Официальная поддержка прямо запрещает импорт произвольной custom ROM; custom device template не равен своей платформенной сборке |

### Размеры машин: что известно, что оценка

* Официальная AOSP requirements: x86-64, Linux, **64 ГБ RAM и минимум 400 ГБ свободного диска**, из которых 250 ГБ исходники и 150 ГБ сборка. Согласованный запас нужен для артефактов и повторных сборок.
* Практический кандидат объединённого build/test-хоста: 16 vCPU, 64 ГБ RAM, 600 ГБ SSD. Это выбор из опубликованных ресурсов, не гарантия времени сборки или уже доступная нам машина.
* Для отдельного boot-хоста начать проверку доступности с Linux/KVM, 4 vCPU, 16 ГБ RAM и места для всего распакованного комплекта и userdata. Это **планировочная оценка**, не официальный минимальный порог и не результат нашего прогона. Гостю сначала дать 4 ГБ для проверки инфраструктуры, затем отдельно 2 ГБ для целевого сценария, сохранив обе конфигурации.

## Почему обычный VPS может не подойти

Compute Engine поддерживает Linux KVM nested virtualization, но не на всех VM: официальная страница исключает E2, ARM, большинство AMD (с оговоркой про N4D) и часть memory-optimized серий. Intel N2 — кандидат, но надо проверить текущую серию/зону/политику организации и явно включить nested virtualization. Не использовать старый совет «подойдёт любой VPS».

Перед запуском на выделенном хосте:

```bash
uname -m
ls -l /dev/kvm
test -r /dev/kvm && test -w /dev/kvm
grep -c -w 'vmx\|svm' /proc/cpuinfo
free -h
df -h .
```

Флаги CPU без доступного `/dev/kvm` недостаточны. Docker без проброса KVM не создаст аппаратную виртуализацию. В облаке важны также исходящий доступ к Android build artifacts, правила сети и расходы на диски/трафик. Не открывать ADB в интернет: использовать SSH tunnel; WebRTC также публиковать только по контролируемому каналу.

## Настоящая проверка нашей ОС: порядок

1. Выбрать и зафиксировать работоспособную ветку, Cuttlefish target и release config. Наличие строки lunch в документации не доказывает поддержку в выбранной ветке.
2. Подключить `doxaiz_base.mk` к продукту Cuttlefish **до сборки**. `build.sh` проверяет вычисленные пакеты/свойства; это ещё не доказательство состава образа.
3. Собрать image archive и `cvd-host_package.tar.gz`. Сохранить pinned repo manifest, commit DoxaizOS, логи, SHA-256 и ожидаемые version/fingerprint из артефактов сборки. Не брать ожидаемый fingerprint с уже запущенной VM — это сделает тест круговым.
4. Доставить **полный согласованный комплект** на тест-хост. По AOSP host package должен соответствовать той же сборке, что и images. Один `system.img` не является готовым самостоятельным виртуальным телефоном; смешивание требует отдельной процедуры и проверки.
5. В одноразовом каталоге распаковать image archive и host package; установить необходимые host-пакеты/группы по документации Cuttlefish. Проверить `./bin/launch_cvd --help` конкретного комплекта перед выбором параметров.
6. Запустить собственный комплект, не устанавливая APK через adb. Либо из подготовленного Android-дерева использовать acloud для локальной/удалённой собственной сборки.
7. Проверить gates ниже, затем reboot, повторную загрузку, данные после reboot, отсутствие boot loop/crash/ANR, установки приложений и сценарии памяти. Это отдельные этапы, не включённые автоматически в PASS базового скрипта.
8. Затем запускать подходящие platform tests/atest/CTS/VTS для выбранной сборки. Имена тестовых модулей брать из её дерева; не обещать «CTS пройден» на основании одного smoke.
9. Только после этого переносить изменения на A64/Redmi 9A и проверять модем, сенсор, дисплей, камеру, звук, сон, шифрование и зарядку на реальном аппарате.

### Официальные примеры запуска (не выполнены нами)

В распакованном согласованном Cuttlefish-комплекте:

```bash
HOME="$PWD" ./bin/launch_cvd --daemon
./bin/adb devices
```

Из настроенного Android-дерева acloud различает:

```bash
# Свой собранный образ, локальная VM:
acloud create --local-instance --local-image
# Свой собранный образ, удалённая VM (может создать платные ресурсы):
# acloud create --local-image
```

`acloud create` без `--local-image` может выбрать готовую сборку Google, а не DoxaizOS. Успешная загрузка такого образа — только baseline инфраструктуры.

## Базовый приёмочный скрипт ОС, без подмены установкой APK

```bash
python3 scripts/check-firmware.py \
  --serial SERIAL \
  --expected-version VERSION_FROM_BUILD \
  --expected-fingerprint FINGERPRINT_FROM_BUILD_ARTIFACT \
  --output reports/firmware-boot-001
```

Скрипт **только читает** данные: boot_completed, версию/fingerprint, low_ram, SELinux, путь предустановленного Launcher, существующий HOME, Binder-сервисы activity/package/window, память и /data. Не устанавливает APK, не назначает HOME, не запускает Activity, не выполняет root/flash/reboot. Launcher только в `/data/app` не проходит: это предотвращает засчитывание обычного Android с установленным APK как нашего образа.

Каждая команда ADB имеет timeout 30 с. Отчёт создаётся в новом каталоге 0700; отказ и сырые stdout/stderr сохраняются в result.json/файлах. Код 0 — пройдены **только перечисленные baseline gates**, код 1 — отказ. Это не криптографическая аттестация, не CTS и не полная приёмка ОС. Изменённая система может сообщить ложные свойства; происхождение образов проверяется отдельно.

13 offline-сценариев скрипта проверяют его логику на подменённом adb. **Реального прогона check-firmware.py на DoxaizOS ещё не было.**

## Первичные источники

1. AOSP hardware requirements — https://source.android.com/docs/setup/start/requirements
2. Cuttlefish get started (KVM, согласованные images/host package, запуск) — https://source.android.com/docs/devices/cuttlefish/get-started
3. acloud manual (local/remote, own image/Android Build image) — https://android.googlesource.com/platform/tools/acloud/+/refs/heads/master/README.md
4. Compute Engine nested virtualization — https://docs.cloud.google.com/compute/docs/instances/nested-virtualization/overview
5. GitHub larger runner resources и ограничения — https://docs.github.com/en/actions/reference/runners/larger-runners
6. GitHub billing: larger runners платные также для public repo — https://docs.github.com/en/billing/concepts/product-billing/github-actions
7. Genymotion custom ROM restriction — https://support.genymotion.com/hc/en-us/articles/360003105317-Is-it-possible-to-use-a-custom-ROM
8. AOSP atest — https://source.android.com/docs/core/tests/development/atest

Это исследование доступных вариантов, не подтверждение наличия у нас доступа к чужому серверу, аккаунту, бесплатной квоте или права создавать платные ресурсы.

## Подтверждённый отрицательный контроль

[Push CI run 46146279694](https://github.com/Doxaiz/Rust-os-for-android-by-Doxaiz/actions/runs/46146279694), commit `82b7170`, успешно завершён. В настоящем Android Emulator check-firmware.py отказал штатному AOSP по отсутствию ожидаемой версии DoxaizOS; smoke дополнительно проверил точную причину отказа. 13 offline-сценариев проверяют остальные gates. **Положительного запуска собственного образа в этом run нет.**

Проверить список уже подключённых self-hosted runners через текущую GitHub-интеграцию не удалось: API вернул `Resource not accessible by integration` (403). Это ограничение прав, а не доказательство отсутствия runners. Новые ресурсы не регистрировались и не оплачивались.


## Бесплатные ресурсы: проверка на практике

### GitHub Actions public Linux — найден и реально работает

Добавлен отдельный workflow `.github/workflows/firmware-reference.yml`, не APK-тест.
[Run 46146936541](https://github.com/Doxaiz/Rust-os-for-android-by-Doxaiz/actions/runs/46146936541), commit `1f1d65b`: **SUCCESS**, job `reference-os` 2 мин 29 с, гость **4096 МБ / 2 CPU**.

Он действительно запускает Cuttlefish/AOSP и проверяет:

* завершение загрузки и SELinux Enforcing;
* Binder-сервисы activity/package/window;
* запись маркера в userdata и `sync`;
* настоящий `adb reboot`, увеличение Android boot_count и повторную полную загрузку;
* сохранение маркера и работоспособность сервисов после перезагрузки.

Скрипт `reference-os-test.sh` отказывает не-loopback serial и не-Cuttlefish ro.hardware. Это защита от случайного выбора физического аппарата, не криптографическая идентификация. Скрипт изменяет userdata **только одноразовой эталонной VM**, не устанавливает Launcher и не выдаёт её за DoxaizOS. Команды ограничены таймаутами; повторная загрузка — 300 с. Два offline test methods отдельно проверяют успешную оркестрацию и четыре отказа; они не являются OS-тестами.

Использован сторонний action `marcprux/cuttlefish-runner` с зафиксированным commit `3e65049fd8a2c2745eb41dca3431680be5d5ebbd`. До запуска просмотрены action.yml, Linux setup/launch/stop/resolve и публичный успешный [upstream run 45242535240](https://github.com/marcprux/cuttlefish-runner/actions/runs/45242535240) (ubuntu-latest, 3 мин 38 с). Action скачивает images и host tools одного build ID, устанавливает cuttlefish-base, меняет права KVM и настройку AppArmor user namespaces. Поэтому запускается только на одноразовом hosted runner без секретов и write-permissions, не на постоянном пользовательском сервере. APT-пакеты и `latest` AOSP остаются плавающими зависимостями; build ID/target записываются в отчёт. Полной воспроизводимости и верификации SHA образов пока нет.

Артефакт первого run: `cuttlefish-reference-46146936541`, 30 735 байт, SHA-256 из GitHub API `94d18d00077426f5856ceb1bba38b6b429abde5d975db171fed6b40e057ad91e`, хранится 3 дня. Локальное скачивание artifact и полного log через gh не удалось: redirect на внешние Azure/Actions-хосты закончился EOF. Поэтому сырые файлы не просмотрены; PASS подтверждён статусами шагов GitHub API и fail-fast assertions workflow, не локальным анализом логов. Точный Android build ID здесь не угадываем.

Standard hosted Linux для public repo выбран вместо larger runner; workflow отказывается работать для private repo. Новые платные машины/подписки не созданы; отдельный облачный аккаунт не нужен. Free не означает бесконечные ресурсы: сохраняются лимиты job/concurrency/artifacts и правила GitHub. Полную AOSP-компиляцию на стандартном runner не обещаем.

**Ограничение:** этот action не имеет входа для собственного image archive. Для DoxaizOS добавлен отдельный путь доставки и запуска нашего согласованного комплекта — firmware-own.yml; без настоящих артефактов его own-os job остаётся skipped. Успех эталона закрывает вопрос бесплатной площадки для boot/reboot-тестов, но не вопрос сборки и не приёмку нашей прошивки.

### Дополнительный реальный прогон с 2 ГБ

[Run 46147167478](https://github.com/Doxaiz/Rust-os-for-android-by-Doxaiz/actions/runs/46147167478), commit `d38fa33`: **SUCCESS**, job `reference-os` 2 мин 19 с, параметры гостя **2048 МБ / 2 CPU**. Повторены те же boot/SELinux/services/reboot/persistence assertions. Это параметры launch, не измерение эффективной доступной памяти и не доказательство бюджетов FPS/PSS/скорости. Текущий workflow оставлен на 2048 МБ. Время job включает установку/скачивание/тесты, поэтому его нельзя называть временем загрузки ОС.

### Альтернативы без оплаты и почему они пока не выбраны

| Площадка | Проверенный факт | Решение |
|---|---|---|
| CircleCI OSS Free | До 400 000 credits/месяц для public Linux OSS; Android machine поддерживает nested virtualization; классы medium→2xlarge+ имеют 150 ГБ диска, RAM 7.5→64 ГБ | Реальный резервный кандидат для запуска ОС. Нет подключённого CircleCI-аккаунта/проверки доступности класса. 150 ГБ диска меньше официальных 400 ГБ AOSP, поэтому полноценный build-host не подтверждён |
| Cirrus CI | Официально индексируемые FAQ/features указывают 50 compute credits/месяц и максимум 8 CPU для free task | Старые инструкции «безлимитной бесплатной сборки Android» не использовать. Текущие RAM/disk/KVM и доступ аккаунта не подтверждены; не выбран |
| GCE Always Free E2 | E2 исключён из nested virtualization | Не подходит для выбранного KVM-стенда; trial/billing не считать бессрочно бесплатным решением |
| Genymotion | Произвольный custom ROM не поддерживается | Не решает задачу |

Первичные ссылки для бесплатной части:

* GitHub public hosted billing: https://docs.github.com/en/billing/concepts/product-billing/github-actions
* Изученный action и его исходники: https://github.com/marcprux/cuttlefish-runner/tree/3e65049fd8a2c2745eb41dca3431680be5d5ebbd
* CircleCI OSS credits/ограничения: https://circleci.com/docs/guides/plans-pricing/credits/
* CircleCI Android machine/KVM/150GB: https://circleci.com/docs/guides/execute/android-machine-image/
* Cirrus FAQ (индекс поисковика, прямое чтение страницы не удалось): https://cirrus-ci.org/faq/

**До готовой прошивки:** получить бесплатную достаточную сборочную мощность либо честно изменить стратегию производства образа; собрать наш образ с provenance; проверить подготовленную доставку собственного комплекта на реальной нашей сборке; пройти identity gates и системные тесты. Подменять это патчем ro.doxaiz.version поверх чужого stock-образа нельзя.

## Собственный продукт: проверка upstream до сборки

`doxaiz_cf_x86_64_phone` зарегистрирован в vendor/doxaiz/AndroidProducts.mk. При просмотре **точного тега из LineageOS manifest**, а не случайной ветки GitHub, найдены два препятствия для простого inherit overlay: `PRODUCT_IGNORE_ALL_ANDROIDMK := true` (наш Launcher пока Make-prebuilt) и `USE_SOONG_DEFINED_SYSTEM_IMAGE := true` с фиксированным `aosp_shared_system_image`. Кандидат-обёртка отключает эти режимы и PRODUCT_SOONG_ONLY; GNU Make fixture проверяет порядок наследования и значения. Это не доказательство успешной Soong/Make-компиляции; необходимо проверить настоящим lunch/m.

Источники просмотрены 2026-11-23:

* LineageOS manifest, AOSP remote android-17.0.0_r1: https://github.com/LineageOS/android/blob/lineage-24.0/default.xml
* Регистрация/примеры trunk_staging: https://android.googlesource.com/device/google/cuttlefish/+/refs/tags/android-17.0.0_r1/AndroidProducts.mk
* Конкретный product, blob cd1e199f714bcc9c2ad8d69b451b2af7c84e7409: https://android.googlesource.com/device/google/cuttlefish/+/refs/tags/android-17.0.0_r1/vsoc_x86_64_only/phone/aosp_cf.mk

Export/verify собственного комплекта описан в [BUILD.md §12](BUILD.md#12-доставка-собственной-сборки-на-бесплатный-тест-хост). Он не получает сборочную мощность и не запускает образы автоматически. Независимая expected identity берётся из target-files, не из getprop тестируемой VM; согласованность всех build outputs остаётся ответственностью доверенного сборщика.


## Путь собственных образов: инфраструктура и отрицательный контроль

Добавлены `.github/workflows/firmware-own.yml`, `prepare-cuttlefish-host.sh`, `unpack-firmware.py` и `boot-firmware-bundle.sh`. Инструкции/границы доверия — [BUILD.md §12](BUILD.md#12-доставка-собственной-сборки-на-бесплатный-тест-хост).

[Run 46149422383](https://github.com/Doxaiz/Rust-os-for-android-by-Doxaiz/actions/runs/46149422383), commit `6a37aba`: **host prerequisites SUCCESS**, проверены реальная установка cuttlefish-base, создание cvd-сетевых интерфейсов, доступ KVM с обновлёнными группами. **Own firmware boot job SKIPPED**: заявки/собственного образа нет. Общий зелёный workflow не является firmware PASS.

Для проверки нового пути на реальных архивах, не дожидаясь нашей сборки, эталонный workflow дополнен отдельным **stock negative control**. После штатного boot/reboot/persistence и остановки VM он берёт тот же stock image ZIP и host package, создаёт явно синтетическую metadata с заведомо несовпадающей DoxaizOS-версией, распаковывает и запускает их новым own-bundle-скриптом. Требуется отказ именно на version gate — ошибка загрузки или распаковки не засчитывается успешным отрицательным контролем. Синтетический manifest этого теста не является настоящим pinned AOSP manifest; хеши проверяют доставку, не происхождение ОС.

Первый [run 46149504950](https://github.com/Doxaiz/Rust-os-for-android-by-Doxaiz/actions/runs/46149504950) **FAILED** на распаковке: реальные host tools используют symlink launch_cvd, а начальная проверка требовала обычный файл прямо по этому имени. Ошибка найдена настоящим CI, не скрыта. В `3145a40` исправлено: допускается только ссылка, которая разрешается в исполняемый обычный файл **внутри** нового дерева; добавлен regression-сценарий. Дальнейший результат фиксируется отдельно, не предполагается по offline-тестам.

Вне настоящей VM проверены 13 synthetic archive cases (traversal, symlink/child, коллизии, hardlink/FIFO, executable, budget и валидные варианты) и 7 mocked own-boot cases (успех/identity/HOME/старое устройство/hash/output/ошибка stop). Моки не измеряют ОС и не повышают процент готовности.


Повторный [run 46149786233](https://github.com/Doxaiz/Rust-os-for-android-by-Doxaiz/actions/runs/46149786233), commit `3145a40`: **SUCCESS**, включая шаг `Real STOCK rejection through own-bundle boot path (NOT DoxaizOS)`. Реальные Google image ZIP + host package прошли проверку доставки, новый распаковщик и запуск собственным скриптом с 2048 МБ; read-only gate отказал **именно по несовпадению ожидаемой DoxaizOS-версии**. Ошибка загрузки не была принята вместо этого результата. Предыдущий эталонный boot/reboot/persistence в том же job тоже успешен. Это реальная проверка новой оркестрации и отрицательного контроля, **не положительная загрузка DoxaizOS**.

Усиленный контроль отдельно фиксирует stop exit code в cleanup.txt и требует `stop_exit_code=0` для успешного отрицательного контроля: одного факта попытки cleanup недостаточно. [Run 46150286844](https://github.com/Doxaiz/Rust-os-for-android-by-Doxaiz/actions/runs/46150286844), commit `013429d`, **SUCCESS**: повторены реальный stock boot/rejection и проверка успешного cleanup. SHA и полные сырые artifacts локально не анализировались; ссылка на CI/статусы шагов является доступным доказательством выполнения assertions. Общая готовность остаётся 25–30%.


Сопутствующая проверка CI: в [run 46149786184](https://github.com/Doxaiz/Rust-os-for-android-by-Doxaiz/actions/runs/46149786184) старый APK-job не дошёл до эмулятора из-за HTTP 403 на анонимном release-tag API запросе. Это не firmware-ошибка. В `fde803c` tag lookup переведён на уже аутентифицированный gh API, curl оставлен только для случая отсутствия gh; checksum-защита не ослаблена. [Run 46150369686](https://github.com/Doxaiz/Rust-os-for-android-by-Doxaiz/actions/runs/46150369686) **SUCCESS**, включая Scripts, Docs, Rust и Launcher Emulator. Последний снова проверяет только приложение на stock Android, не повышает firmware readiness.

## Начальный HOME: проверка платформенного поведения, а не install/HOME smoke

В `home-policy.yml` добавлен отдельный эксперимент **на изменённом stock Cuttlefish userdebug**, гость 2048 МБ. Только одноразовый github-hosted runner, только local Cuttlefish serial/hardware. Он временно включает overlayfs, помещает существующий проверенный APK в /system/app и экспериментальный XML в /system/etc/preferred-apps, делает reboot для системного сканирования, создаёт свежего пользователя. Это НЕ сборка образа и НЕ DoxaizOS boot; AVB/verity состояние этого эксперимента нельзя выдавать за release-конфигурацию. SELinux не отключается.

Результаты, доступные через GitHub checks/annotations:

* [46151138118](https://github.com/Doxaiz/Rust-os-for-android-by-Doxaiz/actions/runs/46151138118): FAILED, первый свежий пользователь ещё выбирал AOSP Provision. Проверять обычный HOME до завершения первичной настройки некорректно.
* [46151495995](https://github.com/Doxaiz/Rust-os-for-android-by-Doxaiz/actions/runs/46151495995): FAILED, после нормального provisioning вместо Doxaiz остался chooser.
* [46151934586](https://github.com/Doxaiz/Rust-os-for-android-by-Doxaiz/actions/runs/46151934586): FAILED при перезапуске adbd as root (`transport closed`). Helper исправлен: успешный root определяется фактическим `id -u=0` с ограниченным ожиданием/reconnect, а не только кодом команды, которая перезапускает свой транспорт.
* [46152244933](https://github.com/Doxaiz/Rust-os-for-android-by-Doxaiz/actions/runs/46152244933), `b515c42`: FAILED как положительный HOME-тест. Диагностика подтверждает `/system/app/DoxaizLauncher/DoxaizLauncher.apk`, точный XML на устройстве, нормальный provisioning и chooser **после 45 секунд наблюдения без назначения HOME**. Кандидаты: Launcher3 priority=0, Doxaiz priority=0, Settings FallbackHome priority=-1000, HOME holder пуст. Это действительное опровержение XML-alone гипотезы, не «успех прошивки».
* [46152842408](https://github.com/Doxaiz/Rust-os-for-android-by-Doxaiz/actions/runs/46152842408): FAILED при расширении сценария отрицательным контролем и последующим явным пользовательским выбором; по доступным annotations нельзя точно установить упавшую команду. Нельзя объявлять сохранность выбора проверенной. В следующую версию добавлен ERR trace в failure.txt.

Исходя из результата, XML убран из PRODUCT_COPY_FILES и **не требуется export bundle**. Он оставлен как экспериментальный вход отрицательного контроля. Для нашего Cuttlefish source build подготовлено другое решение: stock Launcher3/Quickstep HOME priority=-1 в двух manifest, неизменный Doxaiz APK остаётся с 0; штатный launcher/recents не удаляются. Применение/повторная идемпотентная проверка выполнены на точных исходниках LOS Launcher3 `3e0e4f1955992788768547ae2c4115537bc957a6`. Helper включён в build.sh только для собственного CF-таргета и отказывает при missing/drift. 3 source-patch fixture cases и два дополнительных mock build cases проверяют интеграцию; **настоящей компиляции и проверки этого решения в образе пока нет**. Подробности и первичные исходники — [LAUNCHER.md](LAUNCHER.md).

Последний эксперимент [46153393558](https://github.com/Doxaiz/Rust-os-for-android-by-Doxaiz/actions/runs/46153393558), `8aa9f32`: **финальный результат не подтверждён**. `gh run watch` завершился с 0, но последняя полученная сводка ещё показывала running; дополнительный `gh run view` вернул HTTP403 `API rate limit exceeded`. Поэтому не считаем этот run SUCCESS и не утверждаем, что явный выбор пережил reboot. Лимит GitHub API не является ошибкой аутентификации; новые токены не запрашивались, обход лимита не предпринимался. Для следующих наблюдений задавать больший interval вместо частого default polling.

Локально после последних изменений: 17 unittest methods (включая вложенные сценарии) PASS, это не 17 прогонов ОС. Общая готовность остаётся 25–30%; blocker полной сборки собственного образа не снят.

## Усиление приёмки: ядро действительно перезагрузилось, identity не потеряна

Добавлен общий `scripts/check-os-lifecycle.py`; собственный bundle-runner использует последовательность:

1. `check-firmware.py` с version/fingerprint из проверенной metadata сборки — **до** изменения userdata.
2. Lifecycle: guard local serial + Cuttlefish + явный флаг разрешения; Enforcing/core services; корректный kernel boot UUID; случайный marker в /data/local/tmp; sync и reboot; ожидание **нового UUID ядра**, увеличения boot_count и sys.boot_completed=1; проверка marker/fingerprint continuity/служб/SELinux, удаление marker.
3. **Повторный** `check-firmware.py` с прежними независимыми expected значениями. Например, другой HOME после reboot или пропавший ro.doxaiz.version дают отказ — тест не выполняет set-home-activity, install или setprop, чтобы его скрыть.
4. Внешний EXIT trap сохраняет диагностику и останавливает Cuttlefish, в том числе при отказе lifecycle/after-gates.

Общее ожидание повторной загрузки ограничено monotonic deadline: каждый probe получает только оставшееся время. Отсутствующий/неизменившийся UUID не заменяется одним boot_count. Hardware property — лишь guard от случайного выбора аппарата, не доверенная идентификация. Перед выполнением lifecycle на своём образе уже должны пройти независимые firmware gates.

Reference wrapper теперь вызывает тот же общий код и пишет явный `NOT DoxaizOS`. Старые успешные reference runs проверяли прежнюю реализацию; они **не являются доказательством** нового UUID-гейта. Stock negative own-bundle control по-прежнему обязан остановиться на первом version gate, до reboot-сценария своей ОС.

Дополнительные /proc/meminfo, /proc/swaps, PSI, ZRAM mm_stat/algorithm/disksize сохраняются до/после как сырые файлы. Отсутствующие интерфейсы записываются `unavailable`, не подменяются нулями или «бюджет выполнен». Это не бенчмарк, не подтверждение активной настройки ZRAM и не гарантия 2-ГБ Redmi.

Локальная проверка: 19 unittest methods PASS с вложенными сценариями. В новом lifecycle suite 18 cases: успешный/восстановившийся транспорт, не та VM/незавершённая загрузка, плохой UUID, отказ reboot, неизменный UUID/счётчик, недогрузка, потеря marker, смена fingerprint, Permissive/потеря службы после reboot, отсутствующая необязательная диагностика, cleanup failure, adb timeout/missing, частичный write failure. Отдельно проверены consent/serial/existing-report guards. В own-runner 10 mocked cases, включая HOME/version regression после reboot и запуск cleanup при неудачной перезагрузке. Всё это **проверка логики**, не настоящий Android boot.

Первый `git push` после локального commit a199602 завершился `gnutls_handshake() failed`, `gh api rate_limit` — EOF. Повторная публикация a199602 и c918520 в рабочую ветку прошла успешно. Это были транспортные ошибки, не установленная ошибка аутентификации; новые ключи/пароли не запрашивались. Внешний результат новой версии пока не подтверждён: нельзя утверждать, что новый workflow уже прошёл. Общая готовность DoxaizOS остаётся 25–30%.

### Уточнение отрицательного HOME-контроля

Через восстановившийся API подтверждён итог run **46153393558: FAILURE** (check-run 141004682065). Его `failure.txt` точно указывает строку 156: проверка Doxaiz HOME **после первой перезагрузки**. Следовательно, назначение Doxaiz перед reboot и воспроизведение XML-alone chooser прошли предыдущие проверки, но сохранность выбора после reboot **не подтверждена**; до проверки stock-choice сценарий не дошёл. Это заменяет прежний неизвестный итог этого run, но не объясняет причину регрессии.

Обнаружен недостаток самого эксперимента: до reboot проверялся foreground provisioned secondary user, после reboot — только `am start-user`, то есть возможно фоновый/ещё не разблокированный user. Обновлённый контроль сохраняет resolve/role до foregrounding, затем явно переключается в того же пользователя, снимает keyguard и ограниченно наблюдает resolve (45 с), сохраняя историю и preferred/role. **HOME повторно не назначается.** Потеря выбора по истечении ожидания остаётся FAIL. Это проверяемая гипотеза об условиях теста, не доказанная причина старого отказа. Source-патч Launcher3 по-прежнему не собран.

Offline fixture покрывает отдельный случай background-user chooser → исходный выбор после foregrounding и проверяет ровно два назначения на весь успешный эксперимент (по одному на Doxaiz и stock); lost-choice case остаётся отказом с одним назначением. Эти synthetic результаты не подтверждают поведение Android.


### Подтверждённый реальный прогон нового lifecycle

[Run 46155232856](https://github.com/Doxaiz/Rust-os-for-android-by-Doxaiz/actions/runs/46155232856), commit c918520: **completed / SUCCESS**, job 141010318682. Через GitHub API и `gh run watch --exit-status` подтверждены успешные шаги **Boot reference AOSP firmware and test reboot/persistence** и **Real STOCK rejection through own-bundle boot path**. Для первого шага workflow явно задаёт 2048 МБ, 2 CPU, включает новый общий lifecycle. Значит, новая последовательность UUID/boot_count/marker/SELinux/services действительно выполнена на эталонном Android, а не только на mock.

Stock negative control также SUCCESS: это ожидаемое отклонение стокового образа, **не положительная приёмка DoxaizOS**. Точные UUID, значения boot_count, PSI/ZRAM и сырой отчёт здесь не переписываются: загрузка artifact `cuttlefish-reference-46155232856` завершилась EOF на внешнем artifact storage. Итог workflow подтверждён API; содержимое artifact локально не проверено. Не делать из SUCCESS вывода о соблюдении memory budget или улучшении скорости.

Готовность остаётся **25–30%**: реальная бесплатная лаборатория и общий lifecycle подтверждены, но собственный системный образ не собран. HOME-контроль новой редакции c2e8ba1 запрошен push-trigger, его итог пока отдельно не подтверждён.


### Автоматическое сохранение происхождения перед компиляцией

В `scripts/build.sh` добавлен обязательный source-evidence этап после наложения overlay/HOME patch/проверки APK и до lunch/m. Раньше документация требовала ручной `repo diff`, без которого pinned manifest терял локальную правку Launcher3. Теперь manifest -r и diff сохраняются автоматически в новом каталоге вне out/, вместе с lunch target, Doxaiz commit/worktree status и хешами manifest/diff/APK. Manifest с branch-name вместо SHA, ошибка repo manifest/diff или hash capture не пропускают запуск m. EXIT-отчёт отдельно фиксирует nonzero и фазу отказа; неудачная компиляция не превращается в успешный отчёт происхождения.

Это уменьшает риск потерять source patch при передаче сборки, но **не** решает нехватку build-хоста, не создаёт образы, не архивирует все untracked inputs и не связывает криптографически images/target-files/tools. Полный log и дополнительные inputs надо сохранять отдельно. Новый этап проверен только fake-repo/envsetup fixtures: успешные пути, unpinned manifest, manifest/diff failures и сохранение nonzero статуса. Собственной компиляции по-прежнему нет.


### Результат проверки foreground-гипотезы: она недостаточна

[Run 46155735023](https://github.com/Doxaiz/Rust-os-for-android-by-Doxaiz/actions/runs/46155735023), check-run 141011859114, новая редакция c2e8ba1: **FAILURE**. Через annotations получены наблюдения после первой перезагрузки:

* `doxaiz-choice-background-home.txt`: `com.android.settings/.FallbackHome`.
* `doxaiz-choice-background-role.txt` и `doxaiz-choice-foreground-role.txt`: **оба содержат `com.doxaiz.launcher`**.
* После успешного start-user и переключения foreground история resolve на протяжении ограниченного ожидания содержит `android/com.android.internal.app.ResolverActivity`, не Doxaiz HOME.
* В preferred dump по-прежнему видна запись Provision; это наблюдение, не доказанная причина.

Следовательно, одной смены foreground-контекста/ожидания недостаточно. Более точная формулировка: **HOME role-holder пережил reboot, но фактический resolve HOME не соответствует ему**. Нельзя утверждать ни «роль потеряна», ни «выбор полностью сохранился». Stock-choice фаза не достигнута; положительного теста source-патча Launcher3 по-прежнему нет. Нельзя ослаблять own-firmware gate до проверки одного role-holder: фактический resolve остаётся обязательным. Следующее исследование должно разделить RoleManager holder, preferred activity и набор включённых HOME-компонентов после reboot, а не повторно назначать HOME для зелёного результата.

### Следующий контроль: исключение экспериментального XML из фазы выбора

После run 46155735023 исходная причина ещё не доказана. В предыдущем тесте XML, уже признанный неработающим как initial HOME policy, оставался установленным и во время другого эксперимента — persistence явного выбора. Теперь фазы разделены: сначала точно тот же отрицательный контроль XML/chooser, затем root+remount удаляет **только** `/system/etc/preferred-apps/doxaiz-home.xml`, проверяет отсутствие и выполняет sync. Только после этого назначается явный выбор и начинается reboot-проверка. Отсутствие XML повторно проверяется после каждого reboot; невозможность удаления — FAIL до назначения HOME. APK/Launcher3/Provision не удаляются, settings provisioning не переписываются. Область успешного результата явно содержит **AFTER XML REMOVAL**.

Это изоляция переменной, а не доказательство, что XML был причиной: для такого вывода нужен новый реальный результат. Даже положительный итог этой версии подтвердит лишь explicit-choice persistence без XML в modified-stock experiment; он не подтвердит исходный XML, source-патч priority=-1, первоначальный HOME собственного продукта или сборку DoxaizOS. Production product уже исключает этот XML; own-firmware acceptance остаётся без установки APK/назначения HOME. Offline test проверяет отсутствие XML до назначения, а removal failure запрещает дальнейшие назначения.
