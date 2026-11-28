//! Парсеры вывода диагностики adb (Android 13–17) и проверка бюджетов DoxaizOS.
//!
//! Форматы `dumpsys`/`am start` менялись между ветками Android; если вывод на
//! целевой системе отличается — нужны новые фикстуры. Тестовые примеры синтетические,
//! включая форматы, сверенные с исходниками AOSP; это не замеры Cuttlefish.
//!
//! Бюджеты (стартовая калибровка, калибровать на железе — docs/PERFORMANCE.md):
//!   * холодный старт HOME (`am start -W` → TotalTime) — ≤ 400 мс;
//!   * джанки кадров (`dumpsys gfxinfo`)              — ≤ 5,0 %;
//!   * PSS Doxaiz Launcher (`dumpsys meminfo <pkg>`)  — ≤ 60 МБ.

use crate::meminfo::Verdict;

/// Целевой бюджет холодного старта HOME, миллисекунды.
pub const COLD_START_BUDGET_MS: u64 = 400;
/// Целевая доля джанных кадров, проценты.
pub const JANK_BUDGET_PERCENT: f64 = 5.0;
/// Ориентир p90 по кадру для 60 Гц (16,6 мс), миллисекунды.
pub const P90_FRAME_BUDGET_MS: f64 = 16.0;
/// Целевой бюджет PSS Doxaiz Launcher, КиБ.
pub const LAUNCHER_PSS_BUDGET_KB: u64 = 60 * 1024;

// ---------- am start -W ----------

/// Разобранный вывод `am start -W`.
#[derive(Debug, Default, Clone, PartialEq, Eq)]
pub struct ColdStart {
    pub this_time_ms: Option<u64>,
    pub total_time_ms: Option<u64>,
    pub wait_time_ms: Option<u64>,
    pub saw_complete: bool,
    pub status: Option<String>,
    pub launch_state: Option<String>,
    pub saw_error: bool,
    pub reused_activity: bool,
}

/// Разобрать вывод `adb shell am start -W ...`.
pub fn parse_am_start_output(content: &str) -> ColdStart {
    let mut out = ColdStart::default();
    for line in content.lines() {
        let line = line.trim();
        if let Some(rest) = line.strip_prefix("Status:") {
            out.status = Some(rest.trim().to_string());
        } else if let Some(rest) = line.strip_prefix("LaunchState:") {
            out.launch_state = Some(rest.trim().to_string());
        } else if line.starts_with("Error:") || line.starts_with("Error type ") {
            out.saw_error = true;
        } else if line.starts_with("Warning: Activity not started") {
            out.reused_activity = true;
        } else if let Some(rest) = line.strip_prefix("ThisTime:") {
            out.this_time_ms = rest.trim().parse::<u64>().ok();
        } else if let Some(rest) = line.strip_prefix("TotalTime:") {
            out.total_time_ms = rest.trim().parse::<u64>().ok();
        } else if let Some(rest) = line.strip_prefix("WaitTime:") {
            out.wait_time_ms = rest.trim().parse::<u64>().ok();
        } else if line == "Complete" {
            out.saw_complete = true;
        }
    }
    out
}

/// Проверить холодный старт против бюджета.
pub fn check_cold_start(out: &ColdStart) -> Vec<Verdict> {
    let mut verdicts = Vec::with_capacity(2);

    if out.saw_error || out.status.as_deref().is_some_and(|status| status != "ok") {
        return vec![Verdict::Fail("am start сообщил об ошибке или timeout".to_string())];
    }
    if out.reused_activity || out.launch_state.as_deref().is_some_and(|state| state != "COLD") {
        return vec![Verdict::Unknown(
            "это не подтверждённый холодный старт (warm/hot/повторное использование Activity)".to_string(),
        )];
    }
    if out.status.is_none() || out.launch_state.is_none() {
        verdicts.push(Verdict::Unknown("нет Status: ok и/или LaunchState: COLD".to_string()));
    }

    match out.total_time_ms {
        Some(total) if total <= COLD_START_BUDGET_MS => verdicts.push(Verdict::Pass(format!(
            "TotalTime = {total} мс (бюджет <= {COLD_START_BUDGET_MS} мс)"
        ))),
        Some(total) => verdicts.push(Verdict::Fail(format!(
            "TotalTime = {total} мс — больше бюджета {COLD_START_BUDGET_MS} мс \
             (docs/PERFORMANCE.md §8)"
        ))),
        None => verdicts.push(Verdict::Unknown(
            "TotalTime не найден — запускали с -W? (adb shell am start -W ...)".to_string(),
        )),
    }

    if out.saw_complete {
        verdicts.push(Verdict::Pass("строка Complete найдена — запуск завершён".to_string()));
    } else {
        verdicts.push(Verdict::Unknown(
            "строка Complete не найдена — вывод, похоже, неполный".to_string(),
        ));
    }

    verdicts
}

// ---------- dumpsys gfxinfo <pkg> ----------

/// Сводка из `dumpsys gfxinfo <pkg>` (секция статистики после framestats).
#[derive(Debug, Default, Clone, PartialEq)]
pub struct GfxSummary {
    pub total_frames: Option<u64>,
    pub janky_frames: Option<u64>,
    pub janky_percent: Option<f64>,
    pub p90_ms: Option<f64>,
    pub p95_ms: Option<f64>,
    pub p99_ms: Option<f64>,
}

fn parse_prefixed_number<'a>(line: &'a str, prefix: &str) -> Option<&'a str> {
    line.trim().strip_prefix(prefix).map(str::trim)
}

/// Разобрать «N-процентиль» вида `90th percentile: 12ms`.
fn parse_percentile(line: &str, marker: &str) -> Option<f64> {
    let line = line.trim();
    if !line.starts_with(marker) {
        return None;
    }
    let value = line[marker.len()..]
        .trim()
        .trim_end_matches("ms")
        .trim()
        .parse::<f64>()
        .ok()?;
    Some(value)
}

/// Разобрать сводку `dumpsys gfxinfo <pkg>`.
pub fn parse_gfxinfo_summary(content: &str) -> GfxSummary {
    let mut out = GfxSummary::default();
    for line in content.lines() {
        let line = line.trim();

        if let Some(rest) = parse_prefixed_number(line, "Total frames rendered:") {
            out.total_frames = rest.parse::<u64>().ok();
        } else if let Some(rest) = parse_prefixed_number(line, "Janky frames:") {
            // Вид: "12 (1.11%)"
            let mut parts = rest.split_whitespace();
            if let Some(count) = parts.next() {
                out.janky_frames = count.parse::<u64>().ok();
            }
            if let Some(pct) = parts.next() {
                let cleaned = pct
                    .trim_start_matches('(')
                    .trim_end_matches(')')
                    .trim_end_matches('%');
                out.janky_percent = cleaned.parse::<f64>().ok();
            }
        } else if let Some(v) = parse_percentile(line, "90th percentile:") {
            out.p90_ms = Some(v);
        } else if let Some(v) = parse_percentile(line, "95th percentile:") {
            out.p95_ms = Some(v);
        } else if let Some(v) = parse_percentile(line, "99th percentile:") {
            out.p99_ms = Some(v);
        }
    }
    out
}

/// Проверить джанные кадры против бюджета.
pub fn check_gfxinfo(summary: &GfxSummary) -> Vec<Verdict> {
    let mut verdicts = Vec::with_capacity(2);
    if !matches!(summary.total_frames, Some(frames) if frames > 0) {
        return vec![Verdict::Unknown(
            "нет отрисованных кадров — бюджет jank оценить нельзя".to_string(),
        )];
    }

    match summary.janky_percent {
        Some(pct) if !pct.is_finite() || !(0.0..=100.0).contains(&pct) => {
            verdicts.push(Verdict::Unknown("некорректный процент jank".to_string()));
        }
        Some(pct) if pct <= JANK_BUDGET_PERCENT => verdicts.push(Verdict::Pass(format!(
            "Janky frames = {pct:.2}% (бюджет <= {JANK_BUDGET_PERCENT}%)"
        ))),
        Some(pct) => verdicts.push(Verdict::Fail(format!(
            "Janky frames = {pct:.2}% — больше бюджета {JANK_BUDGET_PERCENT}% \
             (docs/PERFORMANCE.md §9 «Правило 5»: замер на устройстве решает)"
        ))),
        None => verdicts.push(Verdict::Unknown(
            "Janky frames не найден — снять framestats: dumpsys gfxinfo <pkg> (после прогона анимации)".to_string(),
        )),
    }

    match summary.p90_ms {
        Some(p90) if !p90.is_finite() || p90 < 0.0 => {
            verdicts.push(Verdict::Unknown("некорректный p90".to_string()));
        }
        Some(p90) if p90 <= P90_FRAME_BUDGET_MS => verdicts.push(Verdict::Pass(format!(
            "p90 кадра = {p90:.1} мс (ориентир <= {P90_FRAME_BUDGET_MS} мс для 60 Гц)"
        ))),
        Some(p90) => verdicts.push(Verdict::Fail(format!(
            "p90 кадра = {p90:.1} мс — больше ориентира {P90_FRAME_BUDGET_MS} мс (для 60 Гц)"
        ))),
        None => verdicts.push(Verdict::Unknown("p90 не найден во входе".to_string())),
    }

    verdicts
}

// ---------- dumpsys meminfo <pkg> ----------

/// Разобранный TOTAL из `dumpsys meminfo <pkg>`.
#[derive(Debug, Default, Clone, PartialEq, Eq)]
pub struct PkgMeminfo {
    /// TOTAL PSS (первое число строки TOTAL), КиБ.
    pub total_kb: Option<u64>,
}

/// Разобрать PSS: App Summary `TOTAL PSS:`, таблица `TOTAL <числа>`
/// или старый синтетический формат `TOTAL: <числа>`. RSS/SWAP не являются PSS.
/// Явная сводка PSS имеет приоритет перед табличным итогом.
pub fn parse_pkg_meminfo_total(content: &str) -> PkgMeminfo {
    fn first_number(value: &str) -> Option<u64> {
        value.split_whitespace().next()?.replace(',', "").parse().ok()
    }

    let mut table_total = None;
    for line in content.lines() {
        let line = line.trim();
        if let Some(rest) = line.strip_prefix("TOTAL PSS:") {
            if let Some(total_kb) = first_number(rest) {
                return PkgMeminfo { total_kb: Some(total_kb) };
            }
        } else if let Some(rest) = line.strip_prefix("TOTAL:") {
            table_total = table_total.or_else(|| first_number(rest));
        } else {
            let mut fields = line.split_whitespace();
            if fields.next() == Some("TOTAL") {
                // TOTAL RSS:/SWAP: do not parse as numbers and are ignored.
                table_total = table_total.or_else(|| fields.next().and_then(first_number));
            }
        }
    }
    PkgMeminfo { total_kb: table_total }
}

/// Проверить PSS лаунчера против бюджета (60 МБ, docs/ARCHITECTURE.md §4).
pub fn check_pkg_meminfo(info: &PkgMeminfo) -> Vec<Verdict> {
    match info.total_kb {
        Some(kb) if kb <= LAUNCHER_PSS_BUDGET_KB => vec![Verdict::Pass(format!(
            "TOTAL PSS = {} МБ (бюджет <= {} МБ)",
            kb / 1024,
            LAUNCHER_PSS_BUDGET_KB / 1024
        ))],
        Some(kb) => vec![Verdict::Fail(format!(
            "TOTAL PSS = {} МБ — больше бюджета {} МБ (docs/ARCHITECTURE.md §4)",
            kb / 1024,
            LAUNCHER_PSS_BUDGET_KB / 1024
        ))],
        None => vec![Verdict::Unknown(
            "строка TOTAL не найдена — это `dumpsys meminfo <pkg>`, а не общий meminfo?".to_string(),
        )],
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const AM_START_OK: &str = "\
Starting: Intent { act=android.intent.action.MAIN cat=[android.intent.category.HOME] }
Status: ok
LaunchState: COLD
Activity: com.doxaiz.launcher/.MainActivity
ThisTime: 213
TotalTime: 213
WaitTime: 221
Complete
";

    const AM_START_SLOW: &str = "\
Status: ok
LaunchState: COLD
Activity: com.doxaiz.launcher/.MainActivity
ThisTime: 700
TotalTime: 733
WaitTime: 745
Complete
";

    const GFXINFO_OK: &str = "\
Applications Memory Usage: nope
Stats since: 12345ns
Total frames rendered: 1080
Janky frames: 12 (1.11%)
90th percentile: 12ms
95th percentile: 14ms
99th percentile: 28ms
Number Missed Vsync: 2
";

    const GFXINFO_BAD: &str = "\
Total frames rendered: 500
Janky frames: 90 (18.00%)
90th percentile: 24.5ms
95th percentile: 31ms
99th percentile: 60ms
";

    const PKG_OK: &str = "\
** MEMINFO in pid 1234 [com.doxaiz.launcher] **
                   Pss  Private  Private  SwapPss
                   ---  ---      ---      ---
  TOTAL: 46100   38000    1000     500
";

    const PKG_FAT: &str = "\
  TOTAL: 131072   100000   2000     900
";

    #[test]
    fn parses_am_start_ok() {
        let out = parse_am_start_output(AM_START_OK);
        assert_eq!(out.total_time_ms, Some(213));
        assert_eq!(out.this_time_ms, Some(213));
        assert_eq!(out.wait_time_ms, Some(221));
        assert!(out.saw_complete);
        assert!(check_cold_start(&out).iter().all(|v| !matches!(v, Verdict::Fail(_))));
    }

    #[test]
    fn slow_start_fails_budget() {
        let out = parse_am_start_output(AM_START_SLOW);
        let verdicts = check_cold_start(&out);
        assert!(verdicts.iter().any(|v| matches!(v, Verdict::Fail(_))));
    }

    #[test]
    fn parses_gfxinfo_ok() {
        let s = parse_gfxinfo_summary(GFXINFO_OK);
        assert_eq!(s.total_frames, Some(1080));
        assert_eq!(s.janky_frames, Some(12));
        assert_eq!(s.janky_percent, Some(1.11));
        assert_eq!(s.p90_ms, Some(12.0));
        assert_eq!(s.p99_ms, Some(28.0));
        assert!(check_gfxinfo(&s).iter().all(|v| !matches!(v, Verdict::Fail(_))));
    }

    #[test]
    fn janky_start_fails_budget() {
        let s = parse_gfxinfo_summary(GFXINFO_BAD);
        let verdicts = check_gfxinfo(&s);
        assert!(verdicts.iter().filter(|v| matches!(v, Verdict::Fail(_))).count() >= 1);
    }

    #[test]
    fn parses_pkg_meminfo_total() {
        let m = parse_pkg_meminfo_total(PKG_OK);
        assert_eq!(m.total_kb, Some(46100));
        assert!(check_pkg_meminfo(&m).iter().all(|v| !matches!(v, Verdict::Fail(_))));
    }

    #[test]
    fn fat_launcher_fails_budget() {
        let m = parse_pkg_meminfo_total(PKG_FAT);
        let verdicts = check_pkg_meminfo(&m);
        assert!(verdicts.iter().any(|v| matches!(v, Verdict::Fail(_))));
    }

    #[test]
    fn empty_inputs_yield_unknowns() {
        assert!(check_cold_start(&parse_am_start_output(""))
            .iter().all(|v| matches!(v, Verdict::Unknown(_))));
        assert!(check_gfxinfo(&parse_gfxinfo_summary(""))
            .iter().all(|v| matches!(v, Verdict::Unknown(_))));
        assert!(check_pkg_meminfo(&parse_pkg_meminfo_total(""))
            .iter().all(|v| matches!(v, Verdict::Unknown(_))));
    }

    #[test]
    fn aosp_meminfo_table_without_colon() {
        let parsed = parse_pkg_meminfo_total(include_str!("../tests/fixtures/meminfo-table.txt"));
        assert_eq!(parsed.total_kb, Some(46_100));
    }

    #[test]
    fn aosp_summary_pss_not_rss_or_swap() {
        let parsed = parse_pkg_meminfo_total(include_str!("../tests/fixtures/meminfo-summary.txt"));
        assert_eq!(parsed.total_kb, Some(50_000));
    }

    #[test]
    fn rss_swap_and_total_prefixes_are_not_pss() {
        for text in ["TOTAL RSS: 100000", "TOTAL SWAP PSS: 42", "TOTALITY: 12",
                     "TOTAL RSS: 90000\nTOTAL SWAP (KB): 500", "TOTAL PSS: invalid"] {
            assert_eq!(parse_pkg_meminfo_total(text).total_kb, None, "{text}");
        }
    }

    #[test]
    fn summary_takes_priority_over_table_in_either_order() {
        for text in ["TOTAL 123 456\nTOTAL PSS: 789", "TOTAL PSS: 789\nTOTAL 123 456"] {
            assert_eq!(parse_pkg_meminfo_total(text).total_kb, Some(789));
        }
    }

    #[test]
    fn invalid_rows_do_not_hide_valid_pss() {
        let text = "TOTAL: invalid\nTOTAL PSS: N/A\nTOTAL RSS: 9\nTOTAL 46100 3 4";
        assert_eq!(parse_pkg_meminfo_total(text).total_kb, Some(46_100));
    }

    #[test]
    fn zero_frames_cannot_pass_even_with_zero_jank() {
        let summary = parse_gfxinfo_summary(
            "Total frames rendered: 0\nJanky frames: 0 (0.00%)\n90th percentile: 0ms",
        );
        assert!(check_gfxinfo(&summary).iter().all(|v| matches!(v, Verdict::Unknown(_))));
    }

    #[test]
    fn invalid_floating_point_metrics_never_pass() {
        for value in [f64::NAN, f64::INFINITY, f64::NEG_INFINITY, -1.0] {
            let summary = GfxSummary {
                total_frames: Some(100), janky_percent: Some(value), p90_ms: Some(value),
                ..GfxSummary::default()
            };
            assert!(check_gfxinfo(&summary).iter().all(|v| matches!(v, Verdict::Unknown(_))));
        }
    }

    #[test]
    fn timeout_and_launch_errors_fail_even_with_fast_timing() {
        for prefix in ["Status: timeout", "Error: Activity class does not exist", "Error type 3"] {
            let text = format!("{prefix}\nLaunchState: COLD\nTotalTime: 0\nComplete");
            assert!(check_cold_start(&parse_am_start_output(&text))
                .iter().any(|v| matches!(v, Verdict::Fail(_))));
        }
    }

    #[test]
    fn warm_hot_and_reused_activity_are_not_cold_samples() {
        for state in ["WARM", "HOT", "UNKNOWN"] {
            let text = format!("Status: ok\nLaunchState: {state}\nTotalTime: 0\nComplete");
            assert!(check_cold_start(&parse_am_start_output(&text))
                .iter().all(|v| matches!(v, Verdict::Unknown(_))));
        }
        let text = "Warning: Activity not started, its current task has been brought to the front\nStatus: ok\nLaunchState: COLD\nTotalTime: 0\nComplete";
        assert!(check_cold_start(&parse_am_start_output(text))
            .iter().all(|v| matches!(v, Verdict::Unknown(_))));
    }

    #[test]
    fn pkg_total_with_thousands_separator() {
        let m = parse_pkg_meminfo_total("  TOTAL: 1,234,567 500 100 10\n");
        assert_eq!(m.total_kb, Some(1_234_567));
    }
}
