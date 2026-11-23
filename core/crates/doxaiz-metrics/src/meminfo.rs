//! Парсинг `/proc/meminfo` и проверка бюджета памяти (см. docs/ARCHITECTURE.md §4).
//!
//! Зачем: архитектурные целевые бюджеты DoxaizOS (docs/ARCHITECTURE.md, §4)
//! должны проверяться машиной, а не «на глаз» в `adb shell`. Этот крейт:
//!   * `parse_meminfo` — разбирает текстовый вывод `/proc/meminfo`;
//!   * `check_budget`  — сверяет его с бюджетом и печатает PASS/FAIL/????.
//!
//! Зависимостей нет. Используется бинарником `doxaiz-check` и тестами в CI.

/// Разобранные поля `/proc/meminfo` (все значения в КиБ, как отдаёт ядро).
/// Поля `Option`, потому что /proc/meminfo на разных ядрах отличается.
#[derive(Debug, Default, Clone, PartialEq, Eq)]
pub struct MemInfo {
    pub mem_total_kb: Option<u64>,
    pub mem_available_kb: Option<u64>,
    pub mem_free_kb: Option<u64>,
    pub swap_total_kb: Option<u64>,
    pub swap_free_kb: Option<u64>,
}

/// Разобрать вывод `/proc/meminfo`. Неизвестные и кривые строки игнорируем,
/// а не падаем: метрики для человека, не для паники.
pub fn parse_meminfo(content: &str) -> MemInfo {
    let mut info = MemInfo::default();
    for line in content.lines() {
        let Some((key, rest)) = line.split_once(':') else {
            continue;
        };
        let key = key.trim();
        let value_kb = rest
            .split_whitespace()
            .next()
            .and_then(|tok| tok.parse::<u64>().ok());
        match key {
            "MemTotal" => info.mem_total_kb = value_kb,
            "MemAvailable" => info.mem_available_kb = value_kb,
            "MemFree" => info.mem_free_kb = value_kb,
            "SwapTotal" => info.swap_total_kb = value_kb,
            "SwapFree" => info.swap_free_kb = value_kb,
            _ => {}
        }
    }
    info
}

/// Бюджет памяти DoxaizOS для целевого устройства.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Budget {
    /// Минимально допустимое MemAvailable в МиБ после прогрева (1 мин после boot).
    pub min_available_mb: u64,
}

impl Default for Budget {
    /// Целевое значение из docs/ARCHITECTURE.md §4: ≥ 1,0 ГБ свободного ОЗУ.
    fn default() -> Self {
        Budget {
            min_available_mb: 1024,
        }
    }
}

/// Результат одной проверки.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Verdict {
    Pass(String),
    Fail(String),
    Unknown(String),
}

impl std::fmt::Display for Verdict {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Verdict::Pass(msg) => write!(f, "PASS {msg}"),
            Verdict::Fail(msg) => write!(f, "FAIL {msg}"),
            Verdict::Unknown(msg) => write!(f, "???? {msg}"),
        }
    }
}

impl Verdict {
    pub fn is_fail(&self) -> bool {
        matches!(self, Verdict::Fail(_))
    }
}

/// Сверить `info` с бюджетом. Возвращает вердикты в стабильном порядке:
/// MemTotal, MemAvailable, Swap. Пустой вход — все `Unknown`, но без паники.
pub fn check_budget(info: &MemInfo, budget: &Budget) -> Vec<Verdict> {
    let mut out = Vec::with_capacity(3);

    match info.mem_total_kb {
        Some(kb) => out.push(Verdict::Pass(format!("MemTotal = {} МБ", kb / 1024))),
        None => out.push(Verdict::Unknown("MemTotal не найден во входе".to_string())),
    }

    match info.mem_available_kb {
        Some(kb) => {
            let avail_mb = kb / 1024;
            if avail_mb >= budget.min_available_mb {
                out.push(Verdict::Pass(format!(
                    "MemAvailable = {avail_mb} МБ (бюджет >= {} МБ)",
                    budget.min_available_mb
                )));
            } else {
                out.push(Verdict::Fail(format!(
                    "MemAvailable = {avail_mb} МБ — меньше бюджета {} МБ \
                     (docs/ARCHITECTURE.md §4)",
                    budget.min_available_mb
                )));
            }
        }
        None => out.push(Verdict::Unknown(
            "MemAvailable не найден (ядро старше 3.14?)".to_string(),
        )),
    }

    match info.swap_total_kb {
        Some(kb) if kb > 0 => {
            out.push(Verdict::Pass(format!("SwapTotal = {} МБ (zram?)", kb / 1024)))
        }
        Some(_) => out.push(Verdict::Fail(
            "SwapTotal = 0: zram выключен — см. docs/PERFORMANCE.md §2".to_string(),
        )),
        None => out.push(Verdict::Unknown("SwapTotal не найден во входе".to_string())),
    }

    out
}

#[cfg(test)]
mod tests {
    use super::*;

    // Типичный вывод /proc/meminfo на 2-ГБ устройстве с zram 50 %.
    const SAMPLE_OK: &str = "\
MemTotal:        2048000 kB
MemFree:          512000 kB
MemAvailable:    1280000 kB
Buffers:           20000 kB
Cached:           400000 kB
SwapCached:          1000 kB
SwapTotal:       1024000 kB
SwapFree:         900000 kB
";

    const SAMPLE_LOW_RAM: &str = "\
MemTotal:        2048000 kB
MemFree:          100000 kB
MemAvailable:     500000 kB
SwapTotal:       1024000 kB
SwapFree:         100000 kB
";

    const SAMPLE_NO_ZRAM: &str = "\
MemTotal:        2048000 kB
MemAvailable:    1500000 kB
SwapTotal:             0 kB
SwapFree:              0 kB
";

    #[test]
    fn parses_typical_meminfo() {
        let info = parse_meminfo(SAMPLE_OK);
        assert_eq!(info.mem_total_kb, Some(2048000));
        assert_eq!(info.mem_available_kb, Some(1280000));
        assert_eq!(info.swap_total_kb, Some(1024000));
    }

    #[test]
    fn parser_tolerates_garbage() {
        let info = parse_meminfo("not a meminfo\n:::\nMemTotal:\nSwapTotal: хрен\n");
        assert_eq!(info.mem_total_kb, None);
        assert_eq!(info.swap_total_kb, None);
    }

    #[test]
    fn healthy_device_passes_budget() {
        let verdicts = check_budget(&parse_meminfo(SAMPLE_OK), &Budget::default());
        assert!(verdicts.iter().all(|v| !v.is_fail()));
    }

    #[test]
    fn hungry_device_fails_budget() {
        let verdicts = check_budget(&parse_meminfo(SAMPLE_LOW_RAM), &Budget::default());
        assert!(verdicts.iter().any(|v| matches!(v, Verdict::Fail(_))));
    }

    #[test]
    fn zero_swap_fails_budget() {
        let verdicts = check_budget(&parse_meminfo(SAMPLE_NO_ZRAM), &Budget::default());
        assert!(verdicts.iter().any(|v| matches!(
            v,
            Verdict::Fail(msg) if msg.contains("zram")
        )));
    }

    #[test]
    fn empty_input_yields_unknowns_not_panics() {
        let verdicts = check_budget(&parse_meminfo(""), &Budget::default());
        assert_eq!(verdicts.len(), 3);
        assert!(verdicts.iter().all(|v| matches!(v, Verdict::Unknown(_))));
    }
}
