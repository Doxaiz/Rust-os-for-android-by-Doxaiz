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

Следующая доработка отдельно фиксирует stop exit code в cleanup.txt и требует `stop_exit_code=0` для успешного отрицательного контроля: одного факта попытки cleanup недостаточно. SHA и полные сырые artifacts локально не анализировались; ссылка на CI/статусы шагов является доступным доказательством выполнения assertions. Общая готовность остаётся 25–30%.
