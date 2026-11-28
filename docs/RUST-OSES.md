# Готовые ОС на Rust: что реально тянет даже самый слабый телефон

> Честный ответ в одном абзаце. **Готовой Rust-ОС, которую можно прошить на обычный слабый телефон (Snapdragon 425-class, 2 ГБ), сегодня не существует.** Причина не в ядре и не в языке, а в драйверах: модем (проприетарное firmware), GPU, камера, сенсоры, PMIC — у всех OSS-проектов кроме Android/Linux этого нет. В серии на Rust реально работает **BlueOS (Vivo)** — 32 МБ ОЗУ-класс, но только на устройствах Vivo и не как телефон. Для «самого слабого телефона» рабочий путь на 2026 год — **DoxaizOS (Android Go-подобный slim)**: Linux + AOSP, в котором всё больше кода написано на Rust.

*Дата доступа ко всем источникам: 2026-11-23. Звёзды — на 2026-11-23. Нумерация источников продолжает [RESEARCH.md](RESEARCH.md) §6 (там [1]–[44]); ссылки [45]–[54] — в конце этой страницы и в RESEARCH.md §6.*

## 1. Сводная таблица

| # | ОС | Класс | Где реально запускается | Мин. ОЗУ | Лицензия | Слабый телефон? | Вердикт для DoxaizOS |
|---|---|---|---|---|---|---|---|
| 1 | **Android / LineageOS + код на Rust** | Linux-монолит | Все Android-телефоны (миллионы устройств); Linux 6.12 `ashmem` на Rust в Android 16, Rust Binder (6.18), Bluetooth/DNS/keystore/медиа на Rust с 2021 | 2 ГБ (Go) / 1 ГБ исторически | Apache-2.0+ | ✅ **ДА — единственный путь сегодня** | **База DoxaizOS.** [4][5][6][7][43] |
| 2 | **BlueOS / BlueKernel (Vivo)** | микроядро на Rust | Серийно: Vivo Watch 3+, ИИ-терминалы, часы, IoT; ядро открыто 2025-07-31; BlueOS 2 (2024-10) — «first fully Rust-written OS» | **32 МБ заявлено** | Apache-2.0 (kernel) | ❌ не прошивается на чужие телефоны; телефонного железа нет, ставится на свои устройства | **Следим.** Единственный proof «Rust-ядро в серии» на слабом железе. [10][46][47] |
| 3 | **Tock** | embedded-RTOS | Cortex-M / RISC-V: RP2040 (Pico), nRF52, micro:bit, сенсоры; от **64 КБ ОЗУ** | 64 КБ | MIT/Apache-2.0, 6.5k★ | ❌ микроконтроллеры, не телефоны | Учимся, как жить в десятках КБ. [51] |
| 4 | **Xous** (betrusted.io) | микроядро | **Baochip-1x** (400 МГц Vexriscv, 2 МиБ SRAM, открытый кремний), Precursor; pure Rust, message-passing | ~2 МиБ | Apache-2.0, ~1k★ | ❌ нет SoC/GPU/модема телефонов | Эталон «чистый Rust, чистый кремний». [50] |
| 5 | **Hubris** (Oxide) | микроядро | Deeply-embedded Oxide (платежи, манагеры), STM32-класс | ~десятки КБ | MPL-2.0, 3.6k★ | ❌ embedded | Не наш случай; эталон изоляции tasks. [52] |
| 6 | **Redox OS** | микроядерная ОС | ПК: x86_64 (0.9.0, livedisk.iso), i686 «generally working», **aarch64 experimental (RPi 3B+ до shell; aarch64 SMP — начальная, без списка плат)** | ~480 МБ (Orbital idle) | MIT, 16.7k★ | ❌ нет модема/GPU/камеры; USB mass-storage в работе; Orbital на 2 ГБ впритык | «Десктопная» альтернатива; телефону не помогает. [8][49] |
| 7 | **Asterinas** | framekernel на Rust, Linux-ABI | **Только x86_64 VMs** (production-цель); 0.19.0 (2026-10): DRM, **AArch64 как 4-я архитектура**, Asterinas NixOS (само-сборка); 240+ syscalls | ВМ, ~512 МБ-класс | MPL-2.0, 5.1k★ | ❌ x86_64 VM-only; драйверов телефона нет; Linux-модули не грузит никогда | Самый амбициозный «Linux на Rust»; на телефон — когда забудут VMs. [45] |
| 8 | **moss** (hexagonal-sun) | Linux-ABI-совместимое ядро | QEMU aarch64 + Pi 4, Jetson Nano, AMD Kria, i.MX8; Arch aarch64 userspace (bash, BusyBox, coreutils, strace); SMP/EEVDF; 109 syscalls | плата-класс (ГБ) | MIT, ~2k★ | ❌ модем/GPU/камера/сенсоры отсутствуют; сеть TCP/IP и полноценная ФС — в работе | Ближе всего к «телефонному» Rust-ядру; Afflictio — мобильный userspace поверх (скелет). [1][2][3][48][54] |
| 9 | **Theseus** | SAS/SPL safe-Rust OS | x86_64 (ARM WIP); исследовательская | ВМ | MIT, 3.2k★ (2024-09, заглохла) | ❌ нет телефонов | Исследование; не трогаем. [53] |
| 10 | **RustyHermit** | unikernel (одно приложение) | Облако/виртуализация, x86_64/aarch64 | ~МБ-класс | MIT/Apache-2.0 | ❌ не интерактивная ОС | Для одному-аргрегации; не телефон. [52] |

## 2. «Самый слабый телефон» — что доступно фактически

| Сценарий | Что реально поставить | Rust в нём |
|---|---|---|
| 2 ГБ / 16 ГБ Flash, Android 8+ (Treble) | **DoxaizOS / любой slim AOSP или GSI** | Linux + Rust (Binder, ashmem, keystore, BT) |
| Устройства Vivo (часы, ИИ-терминалы) | **BlueOS** | Всё, кроме firmware модема/дисплея |
| Одноплатник (Pi 4 и т.п.) как «телефон» | moss/Asterinas/Redox (исследование) | ядро |
| RP2040-класс ($4) как учебный «самый слабый» | Tock, Xous-on-FPGA | всё |

Модельное железо телефона (модемный DSP, проприетарное firmware) — **всегда проприетарно**, поэтому «телефона на 100 % Rust» в обозримой перспективе не будет ни у кого. BlueOS это решает наличием собственного железа; Android — гигантским корпусом HAL; DoxaizOS — наследием AOSP.

## 3. Если хочется пощупать Rust-ОС прямо сейчас (по возрастанию сложности)

1. `Tock` на Raspberry Pi Pico — переключить светодиод/сенсор, ~30 мин. https://github.com/tock/tock
2. `Xous` на Baochip-1x / эмулятор — чистый Rust end-to-end. https://github.com/betrusted-io/xous-core
3. `Redox 0.9.0` в QEMU / x86_64 livedisk — десктоп на Rust. https://gitlab.redox-os.org/redox-os/redox
4. `Asterinas` в QEMU x86_64 — Linux-ABI на framekernel. https://github.com/asterinas/asterinas
5. `moss` в QEMU aarch64 (или Pi 4) — Linux userspace на Rust-ядре. https://github.com/hexagonal-sun/moss-kernel

## 4. Почему DoxaizOS не ждёт «настоящую» Rust-ОС и как это влияет на план

* **Наследуем AOSP/LineageOS и пишем наш слой на Rust** (doxaiz-perf/metrics/xtask, будущий Binder-сервис на rsbinder — см. ROADMAP этап 6). Каждая веха выше — аргумент в пользу «Rust в новом коде», а не «ядро с нуля».
* **Android уже Rust-heavy в продакшене**: Android 16/ядро 6.12 несёт `ashmem` на Rust, Binder на Rust в 6.18; это закрывает самый горячий IPC-путь без нашего участия. [4][5][6][7]
* **Следить за BlueOS**: если Vivo когда-либо откроет телефонную линейку с BlueOS для разработчиков (или выпустит 2 ГБ-устройство под BlueOS), это отдельный продуктовый трек, не влияющий на DoxaizOS.
* **Если Asterinas/moss дорастут до смартфонного железа** (драйверы модема/GPU в mainline) — оценить как отдельный эксперимент (ROADMAP этапы 8), не блокируя основную линию.

## 5. Источники

45. Asterinas (MPL-2.0): 0.19.0 (2026-10) — DRM, AArch64 4-я архитектура, Asterinas NixOS; framekernel, OSTD, 240+ Linux syscalls; x86_64 VM-only — https://github.com/asterinas/asterinas ; https://asterinas.github.io/book/
46. BlueKernel (Vivo, Apache-2.0), открыт 2025-07-31: ARM32/ARM64/RISCV32/RISCV64, QEMU, 32 МБ ОЗУ (заявлено), интервью + opennet: https://github.com/vivoblueos/kernel ; https://opennet.ru/63649-blueos
47. BlueOS: «first fully Rust-written OS», BlueOS 2 (2024-10), BlueXlink; серийно на Vivo Watch 3 / IoT; Wikipedia (актуальное состояние) — https://en.wikipedia.org/wiki/BlueOS
48. moss-kernel (HexagonalSun): 109 syscalls, SMP/EEVDF, Arch aarch64 userspace, Pi4/Jetson Nano/Kria/i.MX8; ~2k★, MIT — https://github.com/hexagonal-sun/moss-kernel ; анонс 3 месяцев: https://news.ycombinator.com/item?id=47003335
49. Redox 0.9.0: x86_64, i686, aarch64 (RPi 3B+ экспериментально), Orbital, livedisk.iso — https://os.watch/redox/0.9.0 ; https://windowsforum.com/news/redox-os-adds-io_uring-like-ring-buffers-initial-numa-support.446021/
50. Xous + Baochip-1x (400 МГц Vexriscv, 2 МиБ SRAM, RV32E BIO) — 39c3: https://media.ccc.de/v/39c3-xous-a-pure-rust-rethink-of-the-embedded-operating-system
51. Tock OS: Cortex-M/RISC-V, ≥ 64 КБ ОЗУ, MIT/Apache-2.0, 6.5k★ — https://github.com/tock/tock
52. Hubris (Oxide, MPL-2.0) — https://github.com/oxidecomputer/hubris ; RustyHermit (unikernel) — https://github.com/hermit-os/hermit-rs
53. Theseus (MIT, заглох 2024-09) + сравнение Rust-OS: https://github.com/theseus-os/Theseus ; https://github.com/flosse/rust-os-comparison
54. Afflictio (GPL-3.0): Linux-ядро + Rust userspace, скелет — https://github.com/mel0k1/Afflictio
