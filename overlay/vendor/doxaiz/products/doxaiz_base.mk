# DoxaizOS — базовый overlay продукта.
#
# Подключается одной строкой в product make-файл устройства (docs/BUILD.md):
#   $(call inherit-product, vendor/doxaiz/products/doxaiz_base.mk)
#
# Состав:
#   * Doxaiz Launcher (com.doxaiz.launcher) как prebuilt-приложение;
#   * privapp-permissions allowlist (нужен только при подписи platform-ключом);
#   * low-RAM свойства в стиле Android Go (стартовая калибровка — docs/PERFORMANCE.md).
#
# ВАЖНО: значения dalvik/low-ram — осознанно консервативная стартовая точка,
# калибруется замерами на целевом железе (docs/PERFORMANCE.md, «Как измерять»).

# --- Пакеты DoxaizOS ---------------------------------------------------------
PRODUCT_PACKAGES += \
    DoxaizLauncher

# --- low-RAM (модель Android Go) ----------------------------------------------
PRODUCT_PROPERTY_OVERRIDES += \
    ro.config.low_ram=true \
    ro.setupwizard.mode=OPTIONAL \
    dalvik.vm.heapstartsize=8m \
    dalvik.vm.heapgrowthlimit=96m \
    dalvik.vm.heapsize=256m

# Версия ОС, которую видит getprop ro.doxaiz.version — удобно для диагностики
# «а на какой DoxaizOS я сейчас смотрю».
PRODUCT_PROPERTY_OVERRIDES += \
    ro.doxaiz.version=0.1.0 \
    ro.doxaiz.profile=lowram-2gb

# --- privapp-permissions --------------------------------------------------------
# Копируем allowlist в system/etc/permissions. Требуется, если лаунчер собран
# как privileged-приложение (LOCAL_CERTIFICATE := platform). Для режима
# PRESIGNED из комплекта overlay allowlist не нужен, файл безобиден.
PRODUCT_COPY_FILES += \
    vendor/doxaiz/etc/privapp-permissions-doxaiz.xml:$(TARGET_COPY_OUT_SYSTEM)/etc/permissions/privapp-permissions-doxaiz.xml
