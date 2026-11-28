# Doxaiz Launcher как prebuilt-приложение (signature: PRESIGNED).
#
# APK сюда НЕ коммитится — кладётся scripts/fetch-launcher-apk.sh из релиза
# https://github.com/Doxaiz/Doxaiz-android-launcher-/releases (см. docs/LAUNCHER.md).
#
# Режим по умолчанию — PRESIGNED:
#   * лаунчер работает как обычное системное приложение (HOME-роль ему доступна);
#   * не нужен platform key; privapp-permissions allowlist не применяется.
#
# Вариант «полновесное привилегированное системное приложение» — см. комментарии
# внизу файла и docs/LAUNCHER.md, раздел «Подпись platform-ключом».

LOCAL_PATH := $(call my-dir)

include $(CLEAR_VARS)

LOCAL_MODULE := DoxaizLauncher
LOCAL_MODULE_CLASS := APPS
LOCAL_MODULE_SUFFIX := $(COMMON_ANDROID_PACKAGE_SUFFIX)
LOCAL_MODULE_TAGS := optional

# Подпись разработчика лаунчера, APK берём как есть.
LOCAL_CERTIFICATE := PRESIGNED
# Явно отключено на начальном этапе; это НЕ требование PRESIGNED.
# app_prebuilt_internal.mk поддерживает dexpreopt без переподписи APK.
# Оценить preopt отдельно по размеру образа/первой загрузке/холодному старту;
# ускорение и память на нашей сборке пока не измерены.
LOCAL_DEX_PREOPT := false

LOCAL_SRC_FILES := DoxaizLauncher.apk
LOCAL_PREBUILT_MODULE_FILE := $(LOCAL_PATH)/DoxaizLauncher.apk

include $(BUILD_PREBUILT)

# --- Вариант B: platform key (privileged system app) ---------------------------
# Раскомментируйте вместо блока выше, если DoxaizLauncher.apk подписан
# platform key собираемой прошивки (keystore/platform.pk8 + platform.x509.pem,
# см. build/make/target/product/security/). Тогда:
#   LOCAL_CERTIFICATE := platform
#   LOCAL_PRIVILEGED_MODULE := true
#   LOCAL_DEX_PREOPT := true          # или false — если сборка AOT не нужна
#   LOCAL_CERTIFICATE := PRESIGNED    # НЕ ставить
# и обязательно объявите нужные privileged permissions в
# overlay/vendor/doxaiz/etc/privapp-permissions-doxaiz.xml — без allowlist
# privileged permissions не выдаются на Android 10+ (см. docs/LAUNCHER.md).
