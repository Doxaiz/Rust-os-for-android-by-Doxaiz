# DoxaizOS: регистрация продуктов для `lunch`.
#
# AOSP/LineageOS находит AndroidProducts.mk в дереве автоматически
# (список собирается в out/.module_paths/AndroidProducts.mk.list на этапе
# soong/bazel-генерации; канонический путь vendor/<vendor>/<sub>/AndroidProducts.mk).
#
# doxaiz_base.mk сюда НЕ добавляем: это библиотека (inherit-product),
# у неё нет PRODUCT_NAME — standalone-таргет не получится, и lunch
# покажет сломанный комбо. Только полноценные продукты.

PRODUCT_MAKEFILES := \
    $(LOCAL_DIR)/products/doxaiz_gsi.mk \
    doxaiz_cf_x86_64_phone:$(LOCAL_DIR)/products/doxaiz_cuttlefish.mk

COMMON_LUNCH_CHOICES := \
    doxaiz_cf_x86_64_phone-trunk_staging-userdebug
