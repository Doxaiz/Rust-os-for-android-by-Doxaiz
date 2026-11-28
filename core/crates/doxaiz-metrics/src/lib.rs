//! DoxaizOS: парсеры диагностики (/proc/meminfo, am start, dumpsys) и проверка бюджетов.
//!
//! Зачем: архитектурные целевые бюджеты DoxaizOS (docs/ARCHITECTURE.md, §4)
//! должны проверяться машиной, а не «на глаз» в adb. Этот крейт — единственный
//! источник истины по метрикам DoxaizOS вне дерева AOSP:
//!   * [`meminfo`] — MemTotal/MemAvailable/Swap против бюджета RAM;
//!   * [`probe`]   — холодный старт HOME, джанки кадров, PSS пакета.
//!
//! Зависимостей нет. Используется бинарником `doxaiz-check` и тестами в CI.

#![forbid(unsafe_code)]

pub mod meminfo;
pub mod probe;
pub mod psi;

pub use meminfo::{check_budget, parse_meminfo, Budget, MemInfo, Verdict};
pub use probe::{
    check_cold_start, check_gfxinfo, check_pkg_meminfo, parse_am_start_output,
    parse_gfxinfo_summary, parse_pkg_meminfo_total, ColdStart, GfxSummary, PkgMeminfo,
};

pub use psi::{parse_memory_pressure, MemoryPressure, Pressure};
