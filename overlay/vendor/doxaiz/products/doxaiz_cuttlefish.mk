# DoxaizOS build product for the FREE x86_64 Cuttlefish lab, NOT for Redmi.
# Base checked in AOSP android-17.0.0_r1 (LineageOS 24.0 manifest remote tag):
# device/google/cuttlefish/vsoc_x86_64_only/phone/aosp_cf.mk
# Build is not yet executed. Do not claim this product works until lunch/m/boot.
$(call inherit-product, device/google/cuttlefish/vsoc_x86_64_only/phone/aosp_cf.mk)
$(call inherit-product, vendor/doxaiz/products/doxaiz_base.mk)

# The upstream product ignores Android.mk and selects a fixed Soong system
# image. Our prebuilt is currently Android.mk and PRODUCT_PACKAGES must feed
# the generated system image. Explicitly use the mixed Make/Soong path rather
# than silently inheriting a stock, fixed-membership system image.
PRODUCT_IGNORE_ALL_ANDROIDMK := false
USE_SOONG_DEFINED_SYSTEM_IMAGE := false
PRODUCT_SOONG_ONLY := false

PRODUCT_NAME := doxaiz_cf_x86_64_phone
# Keep PRODUCT_DEVICE=vsoc_x86_64_only from upstream for its BoardConfig.
PRODUCT_BRAND := doxaiz
PRODUCT_MANUFACTURER := Doxaiz
PRODUCT_MODEL := DoxaizOS Cuttlefish x86_64
