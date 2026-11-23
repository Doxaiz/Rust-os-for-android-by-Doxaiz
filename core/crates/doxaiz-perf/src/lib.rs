//! DoxaizOS: профили и генерация конфигурации для устройств с низким ОЗУ.
//!
//! Этот крейт — единственный источник истины по «низкоуровневой» части
//! DoxaizOS за пределами дерева AOSP: отсюда `doxaiz-xtask gen-prop` печатает
//! `build.prop`-фрагмент, который docs/BUILD.md предлагает добавить в
//! `vendor/doxaiz/products/doxaiz_base.mk` (или положить рядом как
//! `build.prop`-оверлей). Значения — не «магия»: это стартовая точка,
//! которую обязательно калибровать замерами на целевом устройстве
//! (см. docs/PERFORMANCE.md, «Как измерять»).
//!
//! Модель заимствована у Android Go / low-RAM варианта Android:
//! <https://www.gsmarena.com/google_will_prevent_lowram_phones_from_using_android_11-news-44387.php>

/// Доля физического ОЗУ, отдаваемая под ZRAM-swap. 50 % — консервативная
/// стартовая точка для устройств с ≤ 2 ГБ ОЗУ (compression zstd в ядре).
pub const ZRAM_PERCENT_OF_RAM: u64 = 50;

/// Ниже этого порога (в МиБ) включается low-RAM режим целиком.
pub const LOW_RAM_THRESHOLD_MB: u64 = 3 * 1024;

/// Профиль конфигурации low-RAM устройства.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct LowRamProfile {
    /// Полный физический ОЗУ в МиБ (как его видит getconf / /proc/meminfo,
    /// а не маркетинговые «2 ГБ»).
    pub ram_mb: u64,
    /// Размер ZRAM-swap в МиБ.
    pub zram_mb: u64,
    /// Включать ли низкорамный режим фреймворка (`ro.config.low_ram=true`).
    pub low_ram: bool,
    pub dalvik_heap_start_mb: u64,
    pub dalvik_heap_growth_limit_mb: u64,
    pub dalvik_heap_max_mb: u64,
}

impl LowRamProfile {
    /// Строки в формате `build.prop` (ключ=значение), без пустых строк.
    /// Концовка каждой строки — `\n`, так что результат можно писать в файл
    /// как есть.
    pub fn to_build_prop(&self) -> String {
        let mut out = String::new();
        out.push_str("# DoxaizOS low-RAM profile, сгенерировано doxaiz-xtask gen-prop\n");
        out.push_str("# Значения — стартовая калибровка, проверяйте замерами (docs/PERFORMANCE.md)\n");
        out.push_str(if self.low_ram {
            "ro.config.low_ram=true\n"
        } else {
            "ro.config.low_ram=false\n"
        });
        out.push_str(&format!("dalvik.vm.heapstartsize={}m\n", self.dalvik_heap_start_mb));
        out.push_str(&format!("dalvik.vm.heapgrowthlimit={}m\n", self.dalvik_heap_growth_limit_mb));
        out.push_str(&format!("dalvik.vm.heapsize={}m\n", self.dalvik_heap_max_mb));
        out
    }
}

/// Построить профиль для устройства с `ram_mb` МиБ физического ОЗУ.
///
/// Ступени (стартовая калибровка, не догма):
///   * ≤ 2048 МиБ — класс устройств из задания «2 ГБ ОЗУ»: полный low-RAM,
///     самый маленький лимит роста кучи;
///   * ≤ 3072 МиБ — low-RAM режим, чуть просторнее куча;
///   * > 3072 МиБ — обычный режим, ZRAM всё равно включён (50 %).
pub fn profile_for(ram_mb: u64) -> LowRamProfile {
    let zram_mb = (ram_mb * ZRAM_PERCENT_OF_RAM / 100).max(128);
    let low_ram = ram_mb <= LOW_RAM_THRESHOLD_MB;

    let (start, growth, max) = if ram_mb <= 2048 {
        (8, 96, 256)
    } else if ram_mb <= LOW_RAM_THRESHOLD_MB {
        (16, 144, 384)
    } else {
        (16, 256, 512)
    };

    LowRamProfile {
        ram_mb,
        zram_mb,
        low_ram,
        dalvik_heap_start_mb: start,
        dalvik_heap_growth_limit_mb: growth,
        dalvik_heap_max_mb: max,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn two_gb_device_gets_full_low_ram_profile() {
        let p = profile_for(2048);
        assert!(p.low_ram);
        assert_eq!(p.zram_mb, 1024);
        assert_eq!(p.dalvik_heap_growth_limit_mb, 96);
        assert_eq!(p.dalvik_heap_start_mb, 8);
        assert_eq!(p.dalvik_heap_max_mb, 256);
    }

    #[test]
    fn zram_never_below_128_mib() {
        let p = profile_for(128);
        assert_eq!(p.zram_mb, 128);
    }

    #[test]
    fn four_gb_device_is_not_low_ram() {
        let p = profile_for(4096);
        assert!(!p.low_ram);
        assert_eq!(p.zram_mb, 2048);
        assert_eq!(p.dalvik_heap_growth_limit_mb, 256);
    }

    #[test]
    fn three_gb_device_is_low_ram_with_bigger_heap() {
        let p = profile_for(3072);
        assert!(p.low_ram);
        assert_eq!(p.dalvik_heap_growth_limit_mb, 144);
    }

    #[test]
    fn build_prop_is_well_formed() {
        let p = profile_for(2048);
        let prop = p.to_build_prop();
        for line in prop.lines() {
            if line.starts_with('#') {
                continue;
            }
            let (key, value) = line.split_once('=').expect("каждая строка — ключ=значение");
            assert!(!key.is_empty());
            assert!(!value.is_empty());
        }
        assert!(prop.contains("ro.config.low_ram=true\n"));
        assert!(prop.contains("dalvik.vm.heapgrowthlimit=96m\n"));
    }

    #[test]
    fn build_prop_is_deterministic() {
        assert_eq!(profile_for(2048).to_build_prop(), profile_for(2048).to_build_prop());
    }
}
