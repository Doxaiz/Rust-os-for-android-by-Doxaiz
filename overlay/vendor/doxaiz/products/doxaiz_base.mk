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

# --- lmkd (Low Memory Killer daemon): официальные low-RAM дефолты AOSP ---------
# Источник: source.android.com/docs/core/perf/lmkd (таблица «Configure lmkd in
# Android 11») и lmkd README (android.googlesource.com/platform/system/memory/lmkd).
# Мы фиксируем их явно, чтобы поведение не зависело от значений по умолчанию
# конкретной ветки. Осознанно, не «тюнинг наугад»: это low-RAM колонка таблицы.
#   * use_psi=true (PSI вместо vmpressure; ядро должно быть CONFIG_PSI=y)
#   * psi_partial_stall_ms=200  — low RAM: уведомления приходят раньше, чем HP (70)
#   * psi_complete_stall_ms=700 — критический порог полного простоя
#   * thrashing_limit=30        — low RAM: раньше ограничиваем thrashing (HP: 100)
#   * thrashing_limit_decay=50  — low RAM: быстрее опускаем порог после kill (HP: 10)
#   * swap_free_low_percentage=10 — low RAM: порог «swap голоден» (HP: 20)
#   * swap_util_max=100         — проверка выключена (дефолт)
#   * low/medium/critical=1001/800/0 — стандартные границы, HP тоже
# Тюнинг после замеров — docs/PERFORMANCE.md §3.
PRODUCT_PROPERTY_OVERRIDES += \
    ro.lmk.use_psi=true \
    ro.lmk.psi_partial_stall_ms=200 \
    ro.lmk.psi_complete_stall_ms=700 \
    ro.lmk.thrashing_limit=30 \
    ro.lmk.thrashing_limit_decay=50 \
    ro.lmk.swap_free_low_percentage=10 \
    ro.lmk.swap_util_max=100 \
    ro.lmk.low=1001 \
    ro.lmk.medium=800 \
    ro.lmk.critical=0 \
    ro.lmk.debug=false

# --- privapp-permissions --------------------------------------------------------
# Копируем allowlist в system/etc/permissions. Требуется, если лаунчер собран
# как privileged-приложение (LOCAL_CERTIFICATE := platform). Для режима
# PRESIGNED из комплекта overlay allowlist не нужен, файл безобиден.
PRODUCT_COPY_FILES += \
    vendor/doxaiz/etc/privapp-permissions-doxaiz.xml:$(TARGET_COPY_OUT_SYSTEM)/etc/permissions/privapp-permissions-doxaiz.xml \
    vendor/doxaiz/etc/preferred-apps/doxaiz-home.xml:$(TARGET_COPY_OUT_SYSTEM)/etc/preferred-apps/doxaiz-home.xml
