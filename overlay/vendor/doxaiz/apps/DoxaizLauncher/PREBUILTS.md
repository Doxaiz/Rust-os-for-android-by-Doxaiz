# DoxaizLauncher.apk — не коммитится

Сюда `scripts/fetch-launcher-apk.sh` скачивает последний релизный APK лаунчера
из https://github.com/Doxaiz/Doxaiz-android-launcher-/releases.

Файл `DoxaizLauncher.apk` в git не попадает (см. `.gitignore`):
* APK — собранный артефакт, а не исходник;
* подпись APK меняется независимо от этого репозитория;
* `git log` не должен раздуваться бинарниками.

Не кладите сюда keystore и platform key — это секреты сборки, их место —
только в вашем закрытом хранилище/CI secrets.
