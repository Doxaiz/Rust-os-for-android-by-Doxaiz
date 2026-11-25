# Релизы и OTA-обновления DoxaizOS

Как из собранного дерева LineageOS/AOSP получить подписанный образ, который обновляет телефон по воздуху без потери данных — и при необходимости откатывается.

> **Область действия:** этот документ — про **per-device** OTA (обновление живого телефона с установленным DoxaizOS). Для **GSI-поставки** (любой Treble-телефон) стандартный recovery-OTA неприменим: обновление = повторная прошивка нового `system.img` (для major-версий желателен `fastboot -w`). См. [GSI.md](GSI.md) и [BUILD.md](BUILD.md) §8.3.

## 1. Термины

| Термин | Что это |
|---|---|
| **target-files** | zip со ВСЕМИ файлами образа + метаданными сборки (`<model>-target_files-*.zip` из `mka dist`) |
| **OTA-пакет** | инкрементальное или полное обновление (`ota_from_target_files`) — то, что скачивает recovery/A-B и применяет |
| **AVB / verity** | образы подписаны, проверяются на загрузке |
| **block-based OTA** | современный формат: разностный (delta) по блокам, маленький и быстрый |
| **A/B (seamless)** | обновление во второй слот, перезагрузка → слот переключён; откат = переключение слота |
| **VABC** | Virtual A/B via snapshot — быстрый A/B без полного дублирования данных |

## 2. Порядок релиза (одноразово на версию)

```bash
cd ~/doxaiz-os
source build/envsetup.sh
lunch lineage_<codename>-user          # ФИНАЛЬНАЯ сборка — user, не userdebug!
mka -j$(nproc) dist                    # dist = target-files + образы
```

Артефакты появятся в `out/dist/`. Дальше — подпись. **Ключи никогда не лежат в git** (см. SECURITY.md); ключи выпуска — в закрытом хранилище или CI secrets.

### Подпись target-files

```bash
# Собираем host-инструменты из ТОЙ ЖЕ ветки, что и прошивка:
m otatools
"$ANDROID_HOST_OUT/bin/sign_target_files_apks" \
  -o -d /secure/doxaiz-keys \
  <in>/lineage_<codename>-target_files-<tag>.zip \
  <out>/lineage_<codename>-target_files-<tag>-signed.zip
```

`-d` обязательно принимает каталог ключей; `-o` заменяет OTA verification keys с учётом mapping. Это лишь базовый пример: дополнительные ключи APK/APEX, AVB и vendor-разделов определяются конкретной сборкой. Сверьте `META/apkcerts.txt`, `META/apexkeys.txt` и `META/misc_info.txt`; пример не доказывает, что все test keys заменены. Не вызывайте современный host-бинарник через `python3`.

### Генерация OTA zip

```bash
DOXAIZ_OTA_KEY=/secure/doxaiz-keys/releasekey scripts/ota.sh \
  out/dist/lineage_<codename>-target_files-<tag>-signed.zip \
  <out>/doxaizos-<version>-<codename>.zip
```

`scripts/ota.sh` запускает исполняемый host-инструмент напрямую. Выбор: `DOXAIZ_OTA_TOOL` → `$ANDROID_HOST_OUT/bin/ota_from_target_files` → `$ANDROID_BUILD_TOP/out/host/linux-x86/bin/ota_from_target_files` (или cwd вместо build top). Рекурсивного поиска по дереву нет.

`DOXAIZ_OTA_KEY` — необязательный путь к ключу **без расширения**, передаваемый как `-k`. Без него действует выбор ключа самого releasetools; это не гарантия release-подписи. Для incremental OTA третий аргумент — прежний signed target-files ZIP (`-i`). Старый выходной файл сохраняется при ошибке генерации или проверки ZIP/метаданных; публикация — атомарная замена после успеха. Проверка контейнера **не проверяет подпись, ключи или совместимость OTA с устройством**.

### Проверка перед публикацией

```bash
# 1. OTA — валидный zip с метаданными:
unzip -l out/doxaizos-<version>-<codename>.zip | head -20
python3 - <<'EOF'
import zipfile
z = zipfile.ZipFile("out/doxaizos-<version>-<codename>.zip")
meta = z.read("META-INF/com/android/metadata").decode()
assert "post-build=" in meta and "post-timestamp=" in meta
print("метаданные OTA в порядке")
EOF

# 2. Контрольная сумма:
sha256sum out/doxaizos-<version>-<codename>.zip
```

## 3. Доставка на устройство

* **Через recovery**: `adb sideload doxaizos-<version>-<codename>.zip` (Lineage Recovery / TWRP) — так пользователь «сам» обновляется.
* **Автоматически (LineageOS-схема)**: `ota_allowlist` + Server-less OTA не нужны сторонним сборкам; достаточно публиковать zip на GitHub Releases + приложение-«Проверка обновлений» позже.
* **A/B-устройства**: recovery применяет OTA во второй слот; авто-откат при неудачной загрузке делает сам загрузчик (bootcount).
* **Откат вручную**: A/B → `fastboot set_active other && fastboot reboot`; non-A/B → перепрошить предыдущий образ.

## 4. Публикация релиза

1. Тег `v0.2.0` на ветке релиза; CI (`.github/workflows/ci.yml`) уже проверил Rust/доки/скрипты.
2. `gh release create v0.2.0 --title "DoxaizOS 0.2.0" --notes-file RELEASE_NOTES.md out/doxaizos-<version>-<codename>.zip` (из машины сборщика; публичный CI AOSP не собирает).
3. В CHANGELOG.md появляется раздел `## [0.2.0]`.
4. SHA256 суммы — в релиз-заметках (`sha256sum` из шага проверки).

## 5. Обновление payload'а APK лаунчера без OTA

Лаунчер обновляется независимо: `adb install -r` или F-Droid-репозиторий (Этап 7+). Полный OTA нужен только при изменении системных компонентов/ядра/overlay.

## 6. Чеклист релиза

- [ ] `cargo test --workspace` зелёный, `doxaiz-xtask verify` зелёный
- [ ] `user`-сборка (не userdebug), подписана release keys
- [ ] SELinux enforcing (`adb shell getenforce` → Enforcing)
- [ ] `ro.doxaiz.version` ≥ версии в CHANGELOG.md
- [ ] образы проверены на Cuttlefish: загрузка, HOME открывается, пакеты ставятся, звонки/SMS (если модем эмулируется), Wi-Fi
- [ ] `fastboot flash` на железе прошёл, 24 ч стабильности
- [ ] OTA применяется ПОВЕРХ предыдущего release-образа без wipe
- [ ] откат проверен (A/B slot switch)
- [ ] релиз опубликован, sha256 в заметках

## 7. Известные подводные камни

* Разные ветки Android → разные пути releasetools-скриптов; всегда `find . -name 'ota_from_target_files*'` внутри дерева.
* `user`-образ без release keys загрузится только с разблокированным загрузчиком — и это правильно: релизные ключи = контроль над подписью.
* Дельта-OTA требует, чтобы сборка-«источник» была доступна сборщику: храните прошлые target-files в закрытом артефактном сторе.
* Публичный GitHub Actions **не** подходит для AOSP-сборки (диск ~30 ГБ, время): сборка — на машине мейнтейнера, CI — только проверки.

## Примеры реализации, изученные 2026-11-23

Сравнение выполнено по исходникам через GitHub API. Для LineageOS использована доступная ветка `lineage-23.0`: это проверка механики releasetools, а не подтверждение сборки проекта на другой ветке.

* [AOSP ota_from_target_files](https://github.com/aosp-mirror/platform_build/blob/main/tools/releasetools/ota_from_target_files.py): позиционные input/output, incremental `-i`, package key `-k`.
* [LineageOS ota_from_target_files](https://github.com/LineageOS/android_build/blob/lineage-23.0/tools/releasetools/ota_from_target_files.py): CLI генератора для A/B и non-A/B.
* [LineageOS Android.bp](https://github.com/LineageOS/android_build/blob/lineage-23.0/tools/releasetools/Android.bp): `ota_from_target_files` и `sign_target_files_apks` — `python_binary_host`.
* [LineageOS sign_target_files_apks](https://github.com/LineageOS/android_build/blob/lineage-23.0/tools/releasetools/sign_target_files_apks.py): обязательный аргумент каталога у `-d`, OTA key replacement через `-o`, отдельные AVB/APEX-настройки.
* [LineageOS bacon.mk](https://github.com/LineageOS/android_vendor_lineage/blob/lineage-23.0/build/tasks/bacon.mk): публикация уже сформированного OTA и отдельного SHA-256; сама сумма не заменяет подпись.

Локальный regression-набор обёртки: `python3 -m unittest discover -s scripts/tests -v`. OTA-тесты используют mock host tool: реальный payload не строится и на телефон не устанавливается.
