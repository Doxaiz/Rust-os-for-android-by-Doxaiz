# DoxaizOS-GSI — system.img для совместимых ARM64 Treble-устройств.
# ARM32-binder64/A64 (возможный случай Redmi 9A) этим таргетом не покрывается.
#
# Подключается через vendor/doxaiz/AndroidProducts.mk (см. этот же каталог):
#   lunch doxaiz_arm64-userdebug
#   m -j$(nproc)
# Артефакт: out/target/product/generic_arm64/system.img (+ vbmeta.img)
#
# База — штатный GSI-таргет LineageOS `gsi_arm64`
#   (device/generic/common/gsi_arm64.mk; device/generic/common —
#    официальный LOS-проект android_device_generic_common, lineage-24.0;
#    source.android.com: «lunch gsi_arm64-userdebug», образ —
#    out/target/product/generic_arm64/system.img).
#    Состав: core_64_bit + generic_system + gsi_system_ext (SystemUI,
#    Settings, Provision, StorageManager, CarrierConfig…) + gsi_product
#    + gsi_release + VNDK enforcement.
#
# Поверх добавляется doxaiz_base.mk (Doxaiz Launcher как HOME-prebuilt,
# low-RAM/lmkd профайл, ro.doxaiz.*).
#
# ВАЖНО: PRODUCT_DEVICE оставляем generic_arm64 — BoardConfig ищется как
#   device/*/generic_arm64/BoardConfig.mk (AOSP-проект device/generic/arm64).
#   Менять его нельзя: без BoardConfig сборка не стартует.
#
# Честные ограничения GSI — docs/GSI.md §6. Тест на конкретной модели
# без прошивки — через DSU (динамические системные обновления), §5.

$(call inherit-product, device/generic/common/gsi_arm64.mk)
$(call inherit-product, vendor/doxaiz/products/doxaiz_base.mk)

# Свой prebuilt-лаунчер не входит в перечень «разрешённых» артефактов
# CTS-Grade GSI (PRODUCT_ENFORCE_ARTIFACT_PATH_REQUIREMENTS=true в gsi_arm64.mk):
# сборка может упасть на проверке путей. Переводим в relaxed — так же
# поступает штатная minimal-GSI (mgsi/*) в этом же дереве. Per-device
# собирается doxaiz_base.mk и этим не затрагивается.
PRODUCT_ENFORCE_ARTIFACT_PATH_REQUIREMENTS := relaxed

PRODUCT_NAME := doxaiz_arm64
# PRODUCT_DEVICE намеренно НЕ переопределяем (см. шапку файла).
PRODUCT_BRAND := doxaiz
PRODUCT_MANUFACTURER := Doxaiz
PRODUCT_MODEL := DoxaizOS GSI on ARM64
