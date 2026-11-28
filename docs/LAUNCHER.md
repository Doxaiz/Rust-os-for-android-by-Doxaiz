# Интеграция Doxaiz Launcher (рабочий стол DoxaizOS)

Doxaiz Launcher ([репозиторий](https://github.com/Doxaiz/Doxaiz-android-launcher-), MIT, applicationId `com.doxaiz.launcher`) — это рабочий стол DoxaizOS: русский интерфейс, каталог приложений, своя шторка, панель ОЗУ, блокировка экрана. В DoxaizOS он встроен в системный образ как prebuilt-приложение.

> **Факты проверены по исходному коду лаунчера (дата доступа: 2026-11-23, ветка `main`, v1.0.0):**
> * `applicationId`/`namespace` = `com.doxaiz.launcher`; `minSdk 26` · `targetSdk 34` · `compileSdk 34`; `versionName 1.0.0` (versionCode 1).
> * `MainActivity`: intent-filters `MAIN`+`HOME`+`DEFAULT` и `MAIN`+`LAUNCHER`, `launchMode singleTask`, `excludeFromRecents`, portrait.
> * Разрешения включают `QUERY_ALL_PACKAGES` (каталог приложений; нормально для системного prebuilt, Play не нужен), `EXPAND_STATUS_BAR` (шторка), `KILL_BACKGROUND_PROCESSES` («Активные приложения»), `USE_BIOMETRIC` (приватное пространство), `WRITE_SETTINGS` (опциональная яркость/поворот), accessibility-сервис (опционально, двойной тап → выключение экрана, Android 9+). **Нет `INTERNET`** — телеметрии быть не может физически.
> * Аварийный экран `SafeModeActivity` (без HOME-фильтра намеренно) и опциональный `ShizukuProvider`.
> * APK из релиза v1.0.0: `doxaiz-1.0.0.apk`, 873 735 байт (~854 КиБ); релиз публикует `apk-sha256.txt` (скрипт `fetch-launcher-apk.sh` сверяет автоматически).
> * CI лаунчера: эмулятор **API 34 (Android 14)**, снимает кадровые метрики (`.github/workflows/ci.yml` там же).

## 1. Роль HOME

Android получает домашний экран через intent-filter `MAIN` + category `HOME`. У лаунчера он есть. Проверка на устройстве:

```bash
adb shell cmd package query-intent-activities \
    -a android.intent.action.MAIN -c android.intent.category.HOME
```

Ожидаем `com.doxaiz.launcher/.MainActivity` в списке. Выбор по умолчанию:

```bash
adb shell cmd package set-home-activity com.doxaiz.launcher/.MainActivity
# на ряде сборок команда отсутствует → просто жмите «Домой» и выберите Doxaiz
```

### Начальный HOME: реальная ошибка и текущий кандидат исправления

**XML preferred-apps сам по себе не решил задачу.** Это проверено на настоящем stock Cuttlefish, а не предположено по старым примерам. В [run 46152244933](https://github.com/Doxaiz/Rust-os-for-android-by-Doxaiz/actions/runs/46152244933) системный Doxaiz APK и `/system/etc/preferred-apps/doxaiz-home.xml` присутствовали; после нормального provisioning свежего пользователя HOME оставался `android/com.android.internal.app.ResolverActivity`. В списке кандидатов Doxaiz и Launcher3 имели priority=0, Settings FallbackHome — -1000; HOME role holder отсутствовал. Полная причина взаимодействия preferred records/Provision/RoleController пока не доказана. Поэтому XML **убран из PRODUCT_COPY_FILES**, exporter не требует его. Он оставлен только как вход отрицательного эксперимента.

В LineageOS 24.0 Settings.applyDefaultPreferredAppsLPw/readDefaultPreferredActivitiesLPw действительно читает `etc/preferred-apps/*.xml`. Но поддержка синтаксиса ещё не доказывает корректный начальный HOME после настройки. HomeRoleBehavior выбирает fallback по приоритету; при равном приоритете нескольких launcher единственный пакет не выбирается. У текущего HOME role нет defaultHolders-ресурса: выдуманный `config_defaultHome` в overlay сам по себе не поможет.

Кандидат исправления для **нашего Cuttlefish source build**: `patches/lineage-24.0/launcher3-home-fallback.patch` понижает только HOME intent-filter штатного Launcher3/Quickstep до **-1** в двух manifest-файлах. Наш существующий Doxaiz APK остаётся неизменным/PRESIGNED с приоритетом 0. Launcher3/Quickstep не удаляется: остаётся запасной HOME и сервис recents. Это даёт уникальный fallback по прочитанному алгоритму, но **положительная загрузка пересобранной системы ещё не проверена**.

`scripts/build.sh` вызывает `apply-home-fallback-patch.sh` только для doxaiz_cf_x86_64_phone. Helper делает forward/reverse git-apply checks, проверяет итоговый XML и отказывает при несовместимом upstream вместо тихого пропуска. Применение и повторная идемпотентная проверка выполнены на настоящих исходниках Launcher3 commit `3e0e4f1955992788768547ae2c4115537bc957a6`; это проверка source patch, не компиляция приложения. Для GSI/per-device с другими launchers автоматический перенос **не обещается**. При переносе нужны отдельная интеграция начального HOME и проверка пользовательского выбора.

Первое разрешение HOME у свежего пользователя может вести в `com.android.provision/.DefaultActivity`: штатный AOSP Provision выставляет provisioning state и отключает собственную Activity. Нельзя обходить его ручной записью user_setup_complete или отключением pm ради зелёного теста. Начальный HOME проверяется после нормального provisioning/unlock.

`home-policy.yml` теперь хранит **отрицательный контроль**: overlayfs + исходный проверенный APK в /system/app + экспериментальный XML; свежий пользователь, normal provisioning, затем подтверждение chooser/tie/no role holder. После этого отдельные тестовые команды имитируют явный выбор Doxaiz и stock HOME, пытаясь проверить сохранение каждого выбора через reboot. Эти проверки пока не подтверждены успешным финальным run: последний статус не удалось получить из-за лимита GitHub API (подробности FIRMWARE-LAB.md). Это **не проверка работоспособности source patch**: stock Launcher3 в данном опыте не пересобран. Green этого job означает воспроизведение отвергнутого XML-подхода и проверку сохранности явного выбора, не «начальный HOME исправлен».

Изменение HOME командой допускается только для имитации пользовательского действия в этом эксперименте; boot-firmware-bundle/check-firmware по-прежнему не присваивает HOME. Нет init-сервиса, persistent-preferred-activity или команды, возвращающей наш HOME при каждой загрузке.

Источники, прочитанные перед изменением:

* Settings.java (LineageOS snapshot `7d9b4820ef6ac0d72dfd1616094f53b18726e7fe`): https://github.com/LineageOS/android_frameworks_base/blob/7d9b4820ef6ac0d72dfd1616094f53b18726e7fe/services/core/java/com/android/server/pm/Settings.java
* PreferredComponent.java: https://github.com/LineageOS/android_frameworks_base/blob/7d9b4820ef6ac0d72dfd1616094f53b18726e7fe/services/core/java/com/android/server/pm/PreferredComponent.java
* HomeRoleBehavior (Permission snapshot `cdbbb94284627e3876c1c5a5591c619d3687de7b`): https://github.com/LineageOS/android_packages_modules_Permission/blob/cdbbb94284627e3876c1c5a5591c619d3687de7b/PermissionController/role-controller/java/com/android/role/controller/behavior/HomeRoleBehavior.java
* AOSP Provision: https://android.googlesource.com/platform/packages/apps/Provision/+/refs/tags/android-17.0.0_r1/src/com/android/provision/DefaultActivity.java

## 2. Как приложение попадает в образ

1. `scripts/fetch-launcher-apk.sh` скачивает последний релизный APK (и проверяет его sha256 по `apk-sha256.txt` из того же релиза; несовпадение = hard fail) из [Doxaiz-android-launcher-/releases](https://github.com/Doxaiz/Doxaiz-android-launcher-/releases) в `overlay/vendor/doxaiz/apps/DoxaizLauncher/DoxaizLauncher.apk` (или прямо в дерево AOSP, если передать путь).
2. `scripts/apply-overlay.sh` копирует overlay в дерево как `vendor/doxaiz`.
3. `vendor/doxaiz/products/doxaiz_base.mk` добавляет `DoxaizLauncher` в `PRODUCT_PACKAGES`.
4. `vendor/doxaiz/apps/DoxaizLauncher/Android.mk` — модуль `prebuilt_app` (`BUILD_PREBUILT`), по умолчанию в режиме `PRESIGNED`.
5. Для своего Cuttlefish-продукта build.sh применяет source patch начального fallback; работоспособность выбора проверяется только после настоящей сборки. Экспериментальный XML в продукт не копируется.

## 3. Режимы подписи

### A. PRESIGNED (по умолчанию — рекомендуем на старте)

Что есть в overlay:

```makefile
LOCAL_CERTIFICATE := PRESIGNED
LOCAL_DEX_PREOPT := false
```

Особенности:
* ничего не требуется, кроме APK из релизов;
* лаунчер работает как обычное системное приложение;
* роль HOME доступна;
* **privileged permissions не выдаются** (allowlist `privapp-permissions-doxaiz.xml` пуст) — это осознанно;
* обновление лаунчера = замена APK и пересборка образа (или ручное `adb install -r` поверх).

### B. Platform key (privileged system app)

Когда понадобился privileged-функционал (например, WRITE_SECURE_SETTINGS для красивого статусбара на всех сборках):

1. Соберите APK, подписанный platform key именно этой прошивки (`build/make/target/product/security/platform.pk8` + `platform.x509.pem`) — команда вида
   `java -jar signapk.jar platform.x509.pem platform.pk8 app-release-unsigned.apk DoxaizLauncher.apk`.
2. В `Android.mk` переключитесь на:
   ```makefile
   LOCAL_CERTIFICATE := platform
   LOCAL_PRIVILEGED_MODULE := true
   LOCAL_DEX_PREOPT := true
   ```
   (закомментировано в том же файле).
3. В `privapp-permissions-doxaiz.xml` явно перечислите privileged permissions — без allowlist на Android 10+ они не выдаются, даже с platform-подписью.
4. APK с platform-подписью — не для публичной раздачи; он привязан к ключам сборщика.

## 4. Обновление лаунчера без пересборки образа

`adb install -r` поверх установленного APK работает, если подпись совпадает. Для release-раздачи добавьте лаунчер в F-Droid/собственный канал позже; для системного образа важна лишь синхронность версий.

## 5. Проверка после первой сборки

```bash
adb shell dumpsys package com.doxaiz.launcher | grep -E "versionName|flags|signatures" | head
adb shell pm path com.doxaiz.launcher              # ожидаем /system/priv-app/... или /system/app/...
# Холодный старт и кадры:
adb shell am force-stop com.doxaiz.launcher
adb shell am start -W -a android.intent.action.MAIN -c android.intent.category.HOME
adb shell dumpsys gfxinfo com.doxaiz.launcher framestats | head -20
```

## 6. Что НЕ делаем

* Не коммитим APK и ключи в репозиторий (prebuilt кладётся скриптом; ключи — никогда).
* Не форсируем лаунчер системными `set-home-activity` в продакшн-образах — пользователь вправе выбрать другой; DoxaizOS предлагает, не навязывает.
* Не даём privileged permissions «за красивую иконку».

## Обязательная проверка контрольной суммы APK

Загрузчик по умолчанию отказывает, если `apk-sha256.txt` недоступен или не содержит распознаваемую SHA-256. Старый prebuilt сохраняется; несовпадение хеша всегда является ошибкой.

Только для отдельного прогона разработки (не для образов):

```bash
DOXAIZ_ALLOW_UNVERIFIED_APK=1 bash scripts/fetch-launcher-apk.sh
```

Этот режим допускает отсутствие/нечитаемость суммы с явным предупреждением, но **не** несовпадение хеша и **не** повреждённый APK. `scripts/build.sh` принудительно задаёт `DOXAIZ_ALLOW_UNVERIFIED_APK=0` для своего вызова загрузчика независимо от окружения.

SHA-256 рядом с файлом подтверждает согласованность скачанных данных, но не удостоверяет автора. APK и checksum принадлежат одному релизу; компрометация источника или замена обоих файлов этим не обнаруживается. Проверка сертификата подписи APK и стабильности signing key остаётся отдельным незавершённым пунктом. Размер и тег релиза сами по себе не гарантируют неизменность ассета.
