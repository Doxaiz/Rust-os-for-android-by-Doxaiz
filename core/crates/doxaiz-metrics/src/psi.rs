//! Strict, allocation-free parsing of Linux /proc/pressure/memory snapshots.
//!
//! PSI is time stalled on memory, not bytes of free RAM. This module does not
//! invent a performance threshold or treat unavailable PSI as zero pressure.

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Pressure {
    /// Percent of wall time stalled, averaged over 10, 60 and 300 seconds.
    pub avg10: f64,
    pub avg60: f64,
    pub avg300: f64,
    /// Cumulative stalled time in microseconds, not an interval measurement.
    pub total_us: u64,
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct MemoryPressure {
    pub some: Pressure,
    pub full: Pressure,
}

fn parse_row<'a>(fields: impl Iterator<Item = &'a str>) -> Result<Pressure, &'static str> {
    let mut averages = [None; 3];
    let mut total = None;
    for field in fields {
        let (key, value) = field.split_once('=').ok_or("PSI field lacks '='")?;
        if key == "total" {
            if total.is_some() || value.is_empty() || !value.bytes().all(|c| c.is_ascii_digit()) {
                return Err("invalid or duplicate PSI total");
            }
            total = Some(value.parse::<u64>().map_err(|_| "PSI total overflow")?);
            continue;
        }
        let index = match key {
            "avg10" => 0,
            "avg60" => 1,
            "avg300" => 2,
            _ => return Err("unsupported PSI field"),
        };
        if averages[index].is_some() {
            return Err("duplicate PSI average");
        }
        let number = value.parse::<f64>().map_err(|_| "invalid PSI average")?;
        if !number.is_finite() || !(0.0..=100.0).contains(&number) {
            return Err("PSI average must be finite and between 0 and 100");
        }
        averages[index] = Some(number);
    }
    Ok(Pressure {
        avg10: averages[0].ok_or("missing avg10")?,
        avg60: averages[1].ok_or("missing avg60")?,
        avg300: averages[2].ok_or("missing avg300")?,
        total_us: total.ok_or("missing total")?,
    })
}

/// Requires both memory rows. Empty, truncated and unknown formats fail closed.
/// No heap allocation, unsafe code, threads, polling or filesystem mutation.
pub fn parse_memory_pressure(input: &str) -> Result<MemoryPressure, &'static str> {
    if input.len() > 4096 {
        return Err("PSI snapshot exceeds 4096 bytes");
    }
    let mut some = None;
    let mut full = None;
    for line in input.lines().filter(|line| !line.trim().is_empty()) {
        let mut fields = line.split_whitespace();
        let slot = match fields.next() {
            Some("some") => &mut some,
            Some("full") => &mut full,
            _ => return Err("unsupported PSI row"),
        };
        if slot.is_some() {
            return Err("duplicate PSI row");
        }
        *slot = Some(parse_row(fields)?);
    }
    Ok(MemoryPressure {
        some: some.ok_or("missing PSI some row")?,
        full: full.ok_or("missing PSI full row")?,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    const SOME: &str = "some avg10=1.25 avg60=0.50 avg300=0.10 total=123456";
    const FULL: &str = "full avg10=0.25 avg60=0.10 avg300=0.01 total=1234";

    #[test]
    fn parses_values_units_and_reordered_fields() {
        let parsed = parse_memory_pressure(&format!("{SOME}\n{FULL}\n")).unwrap();
        assert_eq!(parsed.some.avg10, 1.25);
        assert_eq!(parsed.some.total_us, 123456);
        assert_eq!(parsed.full.total_us, 1234);
        let reordered = "full total=0 avg300=0 avg60=0 avg10=0\nsome total=18446744073709551615 avg10=100 avg60=0 avg300=0";
        assert_eq!(parse_memory_pressure(reordered).unwrap().some.total_us, u64::MAX);
    }

    #[test]
    fn missing_rows_duplicates_and_unknowns_are_not_zero() {
        for input in [String::new(), SOME.to_owned(), FULL.to_owned(),
                      format!("{SOME}\n{SOME}\n{FULL}"),
                      format!("{SOME}\n{FULL}\n{FULL}"),
                      format!("{SOME}\n{FULL}\nunknown=0"),
                      format!("{SOME} future=0\n{FULL}"),
                      format!("{SOME} avg10=0\n{FULL}")] {
            assert!(parse_memory_pressure(&input).is_err(), "{input}");
        }
        assert!(parse_memory_pressure(&" ".repeat(4097)).is_err());
    }

    #[test]
    fn rejects_invalid_numbers_and_truncation() {
        for value in ["NaN", "inf", "-inf", "-1", "100.01", "", "n/a"] {
            let input = format!("some avg10={value} avg60=0 avg300=0 total=0\n{FULL}");
            assert!(parse_memory_pressure(&input).is_err(), "{input}");
        }
        for total in ["-1", "+1", "1.0", "18446744073709551616", ""] {
            let input = format!("some avg10=0 avg60=0 avg300=0 total={total}\n{FULL}");
            assert!(parse_memory_pressure(&input).is_err(), "{input}");
        }
        assert!(parse_memory_pressure(&format!("some avg10=0 total=0\n{FULL}")).is_err());
    }
}
