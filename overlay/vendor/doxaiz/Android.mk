# DoxaizOS — вендорский overlay для AOSP/LineageOS.
#
# Этот каталог копируется в дерево исходников как vendor/doxaiz
# (см. scripts/apply-overlay.sh). AOSP сам по себе здесь ничего не собирает:
# продуктовые файлы из products/ подключаются одной строкой
#   $(call inherit-product, vendor/doxaiz/products/doxaiz_base.mk)
# в product make-файле вашего устройства (см. docs/BUILD.md, шаг 6).

LOCAL_PATH := $(call my-dir)
