# Минимальная адаптация готовой базы: что реально найдено и что не трогать

## Подтверждённый состав, а не список «мусора» по названию

[Реальный run 46166414296](https://github.com/Doxaiz/Rust-os-for-android-by-Doxaiz/actions/runs/46166414296) SUCCESS, commit 47f33bb. [JSON evidence](evidence/ready-inventory-46166414296.json) получен через API annotations, все 14 проверенных путей представлены. Повторная загрузка прошла continuity SHA-256 pin. Ничего из образа не исполнялось/не удалялось.

Разделы с alias-путями объединены по одинаковым спискам имён. Это **не** идентификация APK/package IDs/подписей и не универсальная дедупликация FS по inode.

| Группа | Число directory entries | Примеры |
|---|---:|---|
| system/app | 23 | CertInstaller, KeyChain, CaptivePortalLogin, PrintSpooler, EasterEgg |
| system/priv-app | 41 | Telecom, TeleService, TelephonyProvider, NetworkStack, PackageInstaller, MtkInCallService |
| product/app | 16 | Aperture, Jelly, LatinIME, webview, Etar, Glimpse, Recorder |
| product/priv-app | 5 | Contacts, Dialer, Eleven, ImsServiceEntitlement, SettingsIntelligence |
| system_ext/app | 2 | Profiles, WAPPushManager |
| system_ext/priv-app | 19 | SystemUI, Settings, LineageSetupWizard, TrebuchetQuickStep, Seedvault |
| etc/init | 80 | lmkd.rc, netd.rc, surfaceflinger.rc, init-debug.rc, phh-remotectl.rc и другие entries |

В шести app-группах всего **106 имён entries**, не «106 фоновых процессов» и даже не гарантированно 106 APK. Некоторые names — overlay/каталоги. 80 init entries — не 80 одновременно работающих служб: есть каталоги, условия запуска и классы.

В проверенных списках не найдены имена `GmsCore`, `PrebuiltGmsCore`, `Phonesky`, `GoogleServicesFramework`. Это согласуется с выбранным Vanilla filename, но **не доказывает отсутствие любых Google-компонентов**: APK manifests/signatures, APEX и остальные пути ещё не разобраны.

## Важное отличие от прежнего AOSP-эксперимента

В этой базе launcher называется **TrebuchetQuickStep**, setup — **LineageSetupWizard**. Нельзя автоматически переносить патч Launcher3 priority=-1 из Android 17 CF-дерева или считать, что здесь работает тот же Provision/HOME сценарий. Базовый готовый образ и его APK остаются неизменными до первого runtime baseline.

После добавления Doxaiz Launcher начальный HOME, роль пользователя и recents должны пройти отдельные проверки именно на этой базе. Замена иконки/branding или назначение HOME через adb не доказывает правильную интеграцию. Существующий Doxaiz Launcher переиспользуется, не переписывается.

## Минимальный первый вариант

1. **Baseline без модификаций.** Сохранить исходный gzip hash; проверить publisher provenance, лицензии/исходники, compatibility/vendor и способ восстановления. Пока это кандидат с userdebug/test-keys, не безопасный production release.
2. **Не удалять системный фундамент:** SystemUI, Settings/SettingsProvider, PackageInstaller, Telephony/Telecom/IMS, NetworkStack, WebView, KeyChain/CertInstaller, input method, permission/role компоненты, setup и launcher/Quickstep fallback. Названия vendor-specific entries не являются разрешением удалить их на MediaTek.
3. **Небольшой слой Doxaiz.** Существующий Launcher; без обязательных новых Rust-служб, фонового оптимизатора, автоматической «чистки RAM» и отключения SELinux. Метод системной интеграции/подписи ещё не реализован и не проверен.
4. **Измерения до тюнинга.** Одинаковые приложения, температура, сеть и время после boot. MemAvailable, PSS/PSI/swap, cold/warm launches, удержание приложений, связь, камера, idle drain. Цель 2 ГБ, не benchmark по размеру ZIP.
5. **Только затем отдельные опциональные изменения.** EasterEgg/BasicDreams/PhotoTable/фоновые картинки — кандидаты для изучения ненужной функциональности, не приказ удаления. Печать/backup/доступность — пользовательские возможности, не безусловный «мусор». Любое удаление — по одному, с dependency/runtime тестом и откатом.

## Незакрытая безопасность до финальной поставки

Нужно отдельно прочитать условия init-debug, debug instrumentation и `phh-remotectl.rc`; само наличие имени **не доказывает активный удалённый доступ**. Нельзя ни игнорировать такие entries, ни заявлять уязвимость без чтения конфигурации и runtime проверки. Security patch строка не заменяет аудит platform/vendor и ключей. Ничего не прошивать по этому документу; инструкция установки намеренно не предоставлена до compatibility проверки.

## Что исправлено в инструментах

Первая попытка структурированного listing дала `unparsed`: parser не принимал пустые separator lines debugfs. Исправлено с regression test; теперь отсутствие usable system/app/priv-app inventory даёт отказ всей inspection. Последующие GitHub notices усекались по длине/числу; вывод заменён компактными группами alias-путей. Финальный JSON evidence восстановлен целиком по восьми группам, покрывающим 14 путей. Старые зелёные property-only runs не выдаются за полный inventory PASS.

Локально: 26 unittest methods, **25 PASS + 1 SKIP** (real-ext4 fixture без e2fsprogs в sandbox). Настоящая инвентаризация выполнена отдельно hosted workflow. **Готовность 25–30%**: образ не загружен на телефоне, расход памяти и улучшение скорости не измерены; производной DoxaizOS image пока нет.
