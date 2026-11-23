//! doxaiz-check: сверить вывод /proc/meminfo с бюджетом DoxaizOS.
//!
//! Использование:
//!   adb shell cat /proc/meminfo > meminfo.txt
//!   cargo run -p doxaiz-metrics -- meminfo.txt
//!
//! Код выхода: 0 — бюджет выполнен (или всё Unknown), 1 — есть FAIL.

use std::fs;
use std::process::ExitCode;

use doxaiz_metrics::{check_budget, parse_meminfo, Budget};

fn usage() {
    eprintln!("Использование: doxaiz-check [meminfo-файл]");
    eprintln!("  по умолчанию читается /proc/meminfo");
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.iter().any(|a| a == "-h" || a == "--help") {
        usage();
        return ExitCode::SUCCESS;
    }
    if args.len() > 1 {
        usage();
        return ExitCode::FAILURE;
    }

    let path = args
        .first()
        .cloned()
        .unwrap_or_else(|| "/proc/meminfo".to_string());

    let content = match fs::read_to_string(&path) {
        Ok(content) => content,
        Err(err) => {
            eprintln!("не прочитать {path}: {err}");
            eprintln!("подсказка: adb shell cat /proc/meminfo > meminfo.txt && doxaiz-check meminfo.txt");
            return ExitCode::FAILURE;
        }
    };

    println!("DoxaizOS budget check: {path}");
    let info = parse_meminfo(&content);
    let verdicts = check_budget(&info, &Budget::default());

    let mut fails = 0usize;
    for verdict in &verdicts {
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
