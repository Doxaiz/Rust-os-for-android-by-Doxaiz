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

## 2. Как приложение попадает в образ

1. `scripts/fetch-launcher-apk.sh` скачивает последний релизный APK (и проверяет его sha256 по `apk-sha256.txt` из того же релиза; несовпадение = hard fail) из [Doxaiz-android-launcher-/releases](https://github.com/Doxaiz/Doxaiz-android-launcher-/releases) в `overlay/vendor/doxaiz/apps/DoxaizLauncher/DoxaizLauncher.apk` (или прямо в дерево AOSP, если передать путь).
2. `scripts/apply-overlay.sh` копирует overlay в дерево как `vendor/doxaiz`.
3. `vendor/doxaiz/products/doxaiz_base.mk` добавляет `DoxaizLauncher` в `PRODUCT_PACKAGES`.
4. `vendor/doxaiz/apps/DoxaizLauncher/Android.mk` — модуль `prebuilt_app` (`BUILD_PREBUILT`), по умолчанию в режиме `PRESIGNED`.
5. В `*_userdebug`-образе после загрузки система видит лаунчер как установленное приложение и назначаемое приложение по умолчанию для HOME.

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
