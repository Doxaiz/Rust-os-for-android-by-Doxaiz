# Устройства для DoxaizOS: как выбрать телефон

Два пути поставки DoxaizOS: **(1) GSI** — универсальный образ для любого устройства с Project Treble (Android 8+): [GSI.md](GSI.md), один образ на тысячи моделей, тест через DSU без прошивки. **(2) per-device порт** — сборка именно под модель: лучшее поведение камеры/DRM/VoLTE, но нужен живой порт LineageOS. Эта страница — про путь (2); про путь (1) — [GSI.md](GSI.md).

**Выбранное пользователем устройство: Redmi 9A, 2 ГБ — [исследование и ограничения](REDMI-9A.md). Готового совместимого образа нет.**

Критерий №1 для per-device: **наличие живого порта LineageOS** на целевую модель.

## 1. Обязательные критерии

| Критерий | Зачем |
|---|---|
| Официальный порт **LineageOS** (не «unofficial») на [lineageos.org/devices](https://lineageos.org/devices/) | Иначе права на выпуск сборки и патчи — под вопросом; официальный порт = готовый device-tree и vendor |
| **2 ГБ ОЗУ (или больше)** | Целевой класс DoxaizOS; больше — только лучше. ⚠️ На 2026-11 официальных портов именно на 2 ГБ почти не осталось — см. §7 |
| 16–32+ ГБ хранилища | Сборка slim-образ (≤ 2,5 ГБ) + userdata + кэши; под 16 ГБ — экономия на приложениях |
| Разблокируемый загрузчик | Без него прошивка невозможна |
| Активные мейнтейнеры порта | Свежесть патчей безопасности и версии Android |

## 2. Методика поиска (не верьте спискам из статей старше года)

1. Откройте [lineageos.org/devices](https://lineageos.org/devices/) — официальный список.
2. Отфильтруйте по вендору/модели вашего телефона и посмотрите **актуальную версию Android и дату последней сборки** — порт «поддерживается», только если были сборки за последние ~3 месяца.
3. Внимательно: у многих старых 2 ГБ-моделей официальные порты уже закрылись (LineageOS обычно держит 2–3 ветки Android). Если вашей модели нет среди официальных — unofficial-порт живёт, пока жив автор, и качество не гарантировано.
4. Реальные low-end на LineageOS 24 (Android 17, по агрегаторам — проверяйте на lineageos.org): **Redmi Note 9** (3/4 ГБ), **Redmi Note 8/8T** (3/4/6), **Redmi Note 10S** (6), **Redmi 12C / POCO C55** (4/6), **Redmi 9** (3/4), **Moto G 5G (2024)**, **Xperia XA2** (3 ГБ). Именно 2 ГБ maintain'овых телефона больше нет — см. §7. [57][58]

## 3. Запасной вариант: Cuttlefish

Если реального устройства нет или его порт умер — виртуальный телефон Cuttlefish (KVM на Linux-хосте) закрывает разработку и все проверки из [PERFORMANCE.md](PERFORMANCE.md) §8, кроме поведения на железе. Это официальный путь AOSP и первый этап ROADMAP (Этап 2).

## 4. Проверка перед покупкой б/у телефона

1. Узнайте точную модель и codename (например, `lineage_<codename>`).
2. Сверьте на lineageos.org/devices, что сборки есть под этот codename и они свежие.
3. Убедитесь, что у конкретного экземпляра разблокируется загрузчик (у Verizon/AT&T/AU-Японские SKU — часто нельзя).
4. Проверьте наличие `recovery.img` и инструкции прошивки конкретно для вашего SKU (carrier-модели могут отличаться).

## 5. Что делать после выбора

Дальше — обычный путь из [BUILD.md](BUILD.md) §8.2/§10/§11:

```bash
lunch lineage_<codename>-userdebug
mka bacon
fastboot flashing unlock   # сотрёт данные
# прошивка по инструкции порта (fastboot или recovery-zip)
```

## 6. Чего не делать

* Не ставить DoxaizOS на телефон без живого порта «по аналогии с похожей моделью» — bricked device вероятнее всего.
* Не брать unofficial-порт без чтения темы порта и проверки даты последнего коммита в device-tree.
* Не ждать, что 2 ГБ-телефон потянет стоковый тяжёлый софт — целевой сценарий DoxaizOS: HOME + базовые приложения + несколько Lite-приложений, а не 30 вкладок Chrome.

## 7. 2 ГБ и LineageOS в 2026 году: честная картина (проверено 2026-11-23)

* **Ни один maintained 2 ГБ-телефон на LineageOS 23/24 не найден.** Все исторические 2 ГБ-порты (Fairphone 2 / FP2, LG G2 / d801, LG K10 / m216, Huawei Mate 2 4G / mt2, Android One 2nd Gen / seed) официально помечены «no longer maintained» в wiki; все они на ядрах 3.4–3.10 — ниже GKI/Treble-минимума, поэтому и закрылись. [56]
* **Jetson Nano 2 GB (porg)** — LineageOS 22.2, но это Android TV, не телефон. [56]
* Минимальный поддерживаемый класс телефонов на LOS 24 — **3–4 ГБ** (Xperia XA2 3 ГБ; крупные Redmi Note — 4–6 ГБ). [57][58]
* **Вывод для DoxaizOS:** на «железных» 2 ГБ единственный реальный путь сегодня — **DoxaizOS-GSI на 2 ГБ-телефоне с Project Treble** (Android 10+; см. [GSI.md](GSI.md)). Per-device официальный порт на 2 ГБ сегодня нереален.
* Если железо можно выбрать: **3–4 ГБ low-end с живым портом** (например, Redmi Note 9/10S) — лучший компромисс «слабое, но реальное».
* Unofficial 2 ГБ-сборки живут, пока жив мейнтейнер (например, Moto E7 Plus «guam» — unofficial LOS 21/22; сам аппарат — 4 ГБ) — качество не гарантировано; перед установкой читайте тему порта. [55]

## Источники

*Нумерация продолжает [RESEARCH.md](RESEARCH.md) §6 ([1]–[54]).*

55. LineageOS Wiki — Moto E7 Plus (guam), unofficial LOS 21+, maintainers Rajin Gangadharan / Deivid Ignacio Parra (сам же аппарат 4 ГБ) — https://wiki.lineageos.org/devices/guam/variant1/
56. LineageOS Wiki — «no longer maintained», 2 ГБ: FP2 https://wiki.lineageos.org/devices/FP2/ · LG G2 (T-Mobile) https://wiki.lineageos.org/devices/d801/ · LG K10 https://wiki.lineageos.org/devices/m216/ · Huawei Mate 2 4G https://wiki.lineageos.org/devices/mt2/ · Android One 2nd Gen https://wiki.lineageos.org/devices/seed/ · Jetson Nano 2 GB [Android TV] https://wiki.lineageos.org/devices/porg/variant2/
57. LineageOS 24 (Android 17) — список устройств, включая low-end (Redmi 12C/POCO C55, Redmi Note 8/9/10S, Redmi 9, Moto G 5G 2024, Xperia XA2) — агрегатор, сверяйте с lineageos.org: https://www.getdroidtips.cv/2026/11/lineageos-24-android-17-download.html · https://androidphoria.com/desarrollo/lineageos-24-novedades-moviles
58. cweiske.de — LineageOS devices (2026, включая guam) — https://cweiske.de/lineage-devices.htm
