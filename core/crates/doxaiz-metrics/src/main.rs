//! doxaiz-check: сверить диагностику устройства с бюджетами DoxaizOS.
//!
//! Режимы:
//!   doxaiz-check meminfo [meminfo-файл]   /proc/meminfo (по умолчанию) или файл
//!   doxaiz-check coldstart <файл>         вывод `adb shell am start -W ...`
//!   doxaiz-check jank <файл>              вывод `adb shell dumpsys gfxinfo <pkg>`
//!   doxaiz-check pss <файл>               вывод `adb shell dumpsys meminfo <pkg>`
//!   doxaiz-check <файл>                   сокращение для `meminfo <файл>`
//!
//! Код выхода: 0 — бюджет выполнен (Unknown не считаются), 1 — есть FAIL.

use std::fs;
use std::path::Path;
use std::process::ExitCode;

use doxaiz_metrics::{
    check_budget, check_cold_start, check_gfxinfo, check_pkg_meminfo, parse_am_start_output,
    parse_gfxinfo_summary, parse_meminfo, parse_pkg_meminfo_total, Budget, Verdict,
};

fn usage() {
    eprintln!("DoxaizOS budget check — doxaiz-check");
    eprintln!("Режимы:");
    eprintln!("  meminfo [файл]   /proc/meminfo (по умолчанию) или файл");
    eprintln!("  coldstart <файл>  вывод adb shell am start -W ...");
    eprintln!("  jank <файл>       вывод adb shell dumpsys gfxinfo <pkg>");
    eprintln!("  pss <файл>        вывод adb shell dumpsys meminfo <pkg>");
    eprintln!("Подсказка: adb shell cat /proc/meminfo > meminfo.txt && doxaiz-check meminfo");
}

fn read_file(path: &str) -> Result<String, ExitCode> {
    fs::read_to_string(path).map_err(|err| {
        eprintln!("не прочитать {path}: {err}");
        ExitCode::FAILURE
    })
}

fn report(verdicts: &[Verdict]) -> ExitCode {
    let mut fails = 0usize;
    for verdict in verdicts {
        println!("{verdict}");
        if verdict.is_fail() {
            fails += 1;
        }
    }
    if fails > 0 {
        eprintln!("бюджет НЕ выполнен: {fails} проверок провалились");
        ExitCode::FAILURE
    } else {
        println!("бюджет выполнен");
        ExitCode::SUCCESS
    }
}

fn meminfo_mode(path: &str) -> ExitCode {
    match read_file(path) {
        Ok(content) => {
            println!("DoxaizOS budget check: meminfo {path}");
            let info = parse_meminfo(&content);
            report(&check_budget(&info, &Budget::default()))
        }
        Err(code) => code,
    }
}

fn requiring_file(args: &[String], usage_line: &str) -> Result<String, ExitCode> {
    match args.first() {
        Some(path) => Ok(path.clone()),
        None => {
            eprintln!("нужен файл с выводом: {usage_line}");
            Err(ExitCode::FAILURE)
        }
    }
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let Some(first) = args.first() else {
        return meminfo_mode("/proc/meminfo");
    };

    match first.as_str() {
        "-h" | "--help" | "help" => {
            usage();
            ExitCode::SUCCESS
        }
        "meminfo" => {
            let path = args.get(1).cloned().unwrap_or_else(|| "/proc/meminfo".to_string());
            meminfo_mode(&path)
        }
        "coldstart" => match requiring_file(&args[1..], "adb shell am start -W ... > coldstart.txt") {
            Ok(path) => match read_file(&path) {
                Ok(content) => {
                    println!("DoxaizOS budget check: coldstart {path}");
                    report(&check_cold_start(&parse_am_start_output(&content)))
                }
                Err(code) => code,
            },
            Err(code) => code,
        },
        "jank" => match requiring_file(&args[1..], "adb shell dumpsys gfxinfo <pkg> > gfx.txt") {
            Ok(path) => match read_file(&path) {
                Ok(content) => {
                    println!("DoxaizOS budget check: jank {path}");
                    report(&check_gfxinfo(&parse_gfxinfo_summary(&content)))
                }
                Err(code) => code,
            },
            Err(code) => code,
        },
        "pss" => match requiring_file(&args[1..], "adb shell dumpsys meminfo <pkg> > pss.txt") {
            Ok(path) => match read_file(&path) {
                Ok(content) => {
                    println!("DoxaizOS budget check: pss {path}");
                    report(&check_pkg_meminfo(&parse_pkg_meminfo_total(&content)))
                }
                Err(code) => code,
            },
            Err(code) => code,
        },
        // Обратная совместимость: `doxaiz-check meminfo.txt` == `meminfo meminfo.txt`
        other if Path::new(other).exists() => meminfo_mode(other),
        other => {
            eprintln!("неизвестный режим «{other}»");
            usage();
            ExitCode::FAILURE
        }
    }
}
