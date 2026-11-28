# Решение по безопасности готовой базы: пока НЕ рекомендовать для финальной установки

## Что реально проверено

[Run 46169653206](https://github.com/Doxaiz/Rust-os-for-android-by-Doxaiz/actions/runs/46169653206), commit 88328bc, **SUCCESS анализа**, не security acceptance. Кандидат повторно совпал с gzip SHA-256 `7000876dee2b0f6f0814431626c495b0f254b00456c88964dee2a68473b3b146`. Из raw ext4 через read-only debugfs извлечены пять текстовых конфигураций; шестой фиксированный путь недоступен.

Полные тексты и их SHA-256 сохранены в [evidence](evidence/ready-security-46169653206.json). Это содержимое реального готового образа, не только просмотр upstream GitHub. Ничего из него не исполнялось, исходящий туннель не создавался, ADB не включался.

## Найден конкретный remote-support механизм

### `/system/etc/init/phh-remotectl.rc`

При `persist.sys.phh.remote=true` конфигурация задаёт `persist.adb.tcp.port=5555`, перезапускает adbd и запускает `phh-remotectl`. При значении `false` — порт 0, restart adbd, stop сервиса.

Объявление сервиса запускает `/system/bin/phh-remotectl.sh` с SELinux label `u:r:phhsu_daemon:s0`. В прочитанном объявлении нет `disabled`. **Нельзя заключать, что при отсутствующем true-trigger сервис гарантированно выключен**: остаются default class/startup ordering, остальные init files, persist properties и runtime. Не утверждаем, что он был активен: образ не загружен.

### `/system/bin/phh-remotectl.sh`

В бесконечном цикле с sleep 10 вызывается:

```text
dbclient -N -p 2222 -y -R <случайный порт>:localhost:5555 android-remote.phh.me
```

Точный текст в evidence содержит выражение вычисления порта и комментарий `FIXME: Don't ignore server pubkey`. Это reverse forwarding локального ADB порта на внешний SSH endpoint; ключ сервера в прочитанной команде явно не закреплён, используется `-y`. Это не обычный idle-компонент, который нужно просто удалить ради RAM.

**Что не доказано:** активный туннель на телефоне, возможность анонимного входа через ADB, bypass ADB authentication, содержимое server-side setup, поведение SELinux, доступность endpoint и вредоносный умысел автора. Наличие remote-support инструмента само по себе не является доказательством заражения. Не подключаться к endpoint для «проверки».

Upstream соответствие для независимого понимания: [TrebleDroid device_phh_treble, commit 94a405915c38e8c09fc01505a56c76c927fb45bf](https://github.com/TrebleDroid/device_phh_treble/tree/94a405915c38e8c09fc01505a56c76c927fb45bf/remote). Это не криптографическое доказательство, что весь бинарный образ собран из этого commit.

## Остальные прочитанные конфигурации

| Файл | Наблюдение | Чего не утверждаем |
|---|---|---|
| init-debug.rc | property-controlled записи в mmc speed/cache sysfs, условные mount/umount debugfs | Не доказывает активный тюнинг накопителя или конкретные effective properties |
| atrace_userdebug.rc | В `post-fs` chmod 0666 для ряда trace interfaces; комментарий оставляет access control SELinux | Не доказывает обход SELinux или фактическую доступность путей |
| logcatd.rc | `service logcatd` имеет `disabled`; старт определяется property-сочетаниями | Не доказывает постоянную запись логов на диск; удалять весь logd нельзя |
| `/system/etc/prop.default` | По этому пути не найден | Не означает безопасные default ro.adb.secure/ro.debuggable; значения могут приходить из других файлов/разделов |

Также уже известны `userdebug/test-keys`. Security patch `2026-11-01` — строка из build.prop, не аудит этих механизмов или vendor телефона.

## Решение для DoxaizOS

**Этот конкретный неизменённый image остаётся только исследовательским кандидатом. Не выдавать его за финальную безопасную прошивку и не советовать немедленную установку.** Положительный audit workflow означает успешное извлечение сведений, а не отсутствие blockers.

До производной финальной поставки необходимо:

1. Исключить remote-support механизм из производного образа как функциональность, а не просто записать `persist.sys.phh.remote=false`. Проверить отсутствие импортов/альтернативных start paths. Не удалять весь `dbclient` или adbd вслепую: зависимости изучать отдельно.
2. Разобрать ADB/debug defaults и release-key/user build стратегию; запретить безусловное включение сетевого ADB. Не отключать SELinux ради совместимости.
3. Зафиксировать все изменения/лицензии/исходники, пересчитать delivery hashes и проверить файловую систему/AVB/подписи. Удаление файла из ZIP не является корректной модификацией ext4 image.
4. Подтвердить runtime: эффективные properties, init service states, listening sockets, USB/ADB authorization, Enforcing, reboot/persistence, связь/камера/шифрование и rollback. Наблюдение только одного property не является доказательством отсутствия сетевого доступа.
5. Лишь после этого интегрировать Doxaiz Launcher с сохранением fallback/recents и измерять RAM/скорость. Никакого автоматического «RAM cleaner».

Эти шаги — **незакрытые требования**, не уже внесённое исправление. Готовый ext4 образ не менялся, собственного hardened image пока нет. При выборе другого prebuilt весь аудит повторяется; слово Vanilla не освобождает от проверки.

## Инструменты и проверка

Inspector теперь сохраняет точные тексты только фиксированных путей, размер и SHA-256, а `runtime_activation` всегда явно `unknown`. Отсутствующие файлы помечаются unavailable; большие тексты не публикуются в notices целиком. Все debugfs вызовы остаются read-only, ограничены timeout/CPU/address space/output size. Данные никогда не интерпретируются shell.

Локально: 26 unittest methods, **25 PASS + 1 SKIP** без e2fsprogs. Настоящий extraction на hosted runner подтверждён отдельно. **Готовность DoxaizOS: 25–30%**. Обнаружение blocker предотвращает небезопасную рекомендацию, но не повышает готовность прошивки.

## Rust: подготовка проверенных замен, пока без изменения ext4

Добавлен host-only crate `core/crates/doxaiz-hardening`, binary `doxaiz-harden-remote`. Без external dependencies, `unsafe`, shell execution, сетевых запросов, root и фоновой службы. На вход получает **два файла, извлечённых из образа**; их содержимое должно побайтно совпасть с reviewed policy из run 46169653206. Несовпадение хотя бы одного файла, symlink/ancestor, oversized/missing input или уже существующий output дают отказ. Input files не изменяются.

```bash
cargo run --release --manifest-path core/Cargo.toml \
  -p doxaiz-hardening --bin doxaiz-harden-remote -- \
  reports/ready-base/inspection/system-etc-init-phh-remotectl.rc.txt \
  reports/ready-base/inspection/system-bin-phh-remotectl.sh.txt \
  reports/ready-base/remote-patch
```

В новом каталоге создаются:

- `phh-remotectl.rc` — только комментарии: без service declaration, imports и property-trigger действий;
- `phh-remotectl.sh` — только shebang, комментарий и `exit 1`, без dbclient/цикла/сетевых команд;
- `NOTICE.txt` — completion record с `image_modified=false`, `boot_tested=false`, `runtime_security_verified=false`. Пишется последним; IO failure оставляет непригодный partial output, повторная запись запрещена.

Это подготовка **двух замен**, а не универсальный security scanner, не полная нейтрализация всех start paths и не готовый hardened ROM. Не копировать файлы вслепую на телефон: ещё нужны image integration, SELinux labels/modes, filesystem/AVB/подписи и runtime проверка. Если где-то есть альтернативный service с тем же script, простой `exit 1` может приводить к рестартам: наличие таких путей надо проверить до применения. Инструмент не трогает adbd/dbclient глобально и не выставляет произвольные «ускоряющие» properties.

Ready-base workflow собирает этот инструмент в release и применяет **к извлечённым текстовым файлам**, сохраняя маленький patch report. Исходный gzip/raw image не изменяется и не распространяется; подготовка замены не снимает запрет рекомендации исходного image. Скопированные `.original` policy inputs сохраняют upstream provenance; новая MIT crate не перелицензирует Android/TrebleDroid firmware. Review лицензий перед redistribution остаётся обязательным.

Rust tests проверяют точные outputs/неизменность inputs, отказ на drift/missing/oversized, повторный output и symlinks. Это host-tool tests, не Android runtime. Файловые race attacks от другого локального пользователя не моделируются; только собственный disposable workspace, без root. Rust здесь используется для нового собственного слоя, а не как заявление об ускорении готового Android.

### Подтверждённый результат Rust-подготовки

Workspace `cargo test` прошёл в полном [CI 46171240670](https://github.com/Doxaiz/Rust-os-for-android-by-Doxaiz/actions/runs/46171240670), commit 6dfdf69, SUCCESS. Первая integration-попытка 46171240687 FAILED: ошибка shell wiring разбила аргументы, программа корректно завершилась с usage exit 2. Исправление de0d786 добавило regression test фактического workflow command с mock cargo.

После исправления [run 46171662508](https://github.com/Doxaiz/Rust-os-for-android-by-Doxaiz/actions/runs/46171662508) **SUCCESS**: готовый gzip снова загружен/сверен, конфигурации извлечены read-only, реальный release Rust binary принял их точные bytes и создал две inert replacement files + NOTICE. [Полный patch evidence](evidence/rust-remote-patch-46171662508.json) получен через API, SHA текстов проверены локально.

**Не путать:** исходный system.img всё ещё НЕ модифицирован; ext4 integration/SELinux/AVB/runtime не выполнены. Это первый реально проверенный Rust patch-preparation шаг, не безопасная готовая прошивка. Общая готовность 25–30%. Локально Python suites: 27 methods, 26 PASS + 1 SKIP; Rust compiler отсутствует в sandbox, его compile/tests выполнены hosted CI.
