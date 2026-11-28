# Эмуляция: что можно проверить без Redmi 9A

## Выбранный тест

Android Emulator, **API 29 / Android 10, x86_64, 2048 МБ RAM**, стандартный AOSP system image, GitHub-hosted Ubuntu с KVM. Запуск задан отдельным обязательным job `android-emulator` в `.github/workflows/ci.yml` для push; на pull_request job пропускается, чтобы не дублировать тяжёлый прогон того же коммита. На каждом новом push тест выполняется снова.

Это **не DoxaizOS system.img** и **не эмулятор Redmi 9A**. Выбор Android 10 связан с исходным поколением Android телефона, но MIUI/vendor, CPU MediaTek, ARM32/Binder64 и накопитель этим не воспроизводятся. 2048 МБ в конфигурации AVD не гарантируют точного совпадения MemTotal с физическим телефоном.

## Сравнение примеров

Источники изучены через GitHub API в ходе этой работы:

| Пример | Применение и ограничения |
|---|---|
| [ReactiveCircus/android-emulator-runner](https://github.com/ReactiveCircus/android-emulator-runner) | Создание AVD, KVM на Ubuntu, `ram-size: 2048M`, boot timeout и запуск скрипта. Action закреплён на commit `a421e43855164a8197daf9d8d40fe71c6996bb0d`, а не плавающем v2 |
| [Google emulator container scripts](https://github.com/google/android-emulator-container-scripts) | Примеры Docker требуют передачи `/dev/kvm`; контейнер сам по себе не решает отсутствие KVM здесь |
| [Google Cuttlefish](https://github.com/google/android-cuttlefish) | Путь испытания собственной Android-сборки, но нужен подходящий образ и виртуализация; у нас образ ещё не собран |
| [AOSP ActivityManagerShellCommand](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-16.0.0_r1/services/core/java/com/android/server/am/ActivityManagerShellCommand.java) | Формат am start -W и различие COLD/WARM/HOT; функциональный smoke ниже не объявляется проверкой холодного старта |

Локально в песочнице не обнаружены Android Emulator, QEMU или `/dev/kvm`. SDK/system image требуют дополнительной загрузки; сборку и запуск собственной ОС здесь не выполняли.

## Проверки scripts/emulator-smoke.sh

1. Отказывается работать с serial без префикса `emulator-` и без `ro.kernel.qemu=1`. Это защита от случайного запуска на телефоне, не средство аутентификации устройства.
2. Устанавливает **действительный релизный APK** после обязательной проверки доступной SHA-256 в downloader.
3. Назначает Doxaiz Launcher домашним экраном, запускает MainActivity, проверяет разрешение HOME, resumed Activity и PID.
4. Сохраняет start.txt, home.txt, activities.txt, PID, свойства эмулятора, скриншот, logcat и сырой диагностический отчёт.
5. Загружает результаты как Actions artifact со сроком хранения 7 дней. Успешный job не публикует прошивку и не является релизом.

В случае ошибки скачивания текст сохраняется отдельно и выводится в annotations. Прохождение теста можно утверждать только после успешного emulator job для соответствующего SHA, а не после успеха Rust/Docs или пропущенного шага.

Для ручного прогона на подготовленном Linux-хосте с запущенным Android Emulator:

```bash
bash scripts/fetch-launcher-apk.sh
DOXAIZ_ADB_TARGET=emulator-5554 bash scripts/emulator-smoke.sh \
  overlay/vendor/doxaiz/apps/DoxaizLauncher/DoxaizLauncher.apk reports/emulator-manual
```

Скрипт изменяет роль HOME и устанавливает приложение на тестовом AVD; используйте одноразовый AVD. Не добавляйте root или прошивочные команды для обхода отказа.

## Что нельзя заключать из PASS

* Не подтверждена сборка overlay или запуск DoxaizOS.
* Не подтверждена совместимость A64/Redmi 9A, звонков, камеры, шифрования или зарядки.
* Не подтверждены бюджет памяти и плавность: x86_64/виртуальный GPU не воспроизводят Helio G25.
* Проверка resumed Activity не проверяет все функции UI и не исключает более поздний crash/ANR.
* API 29 не заменяет отдельные тесты на других версиях Android.
