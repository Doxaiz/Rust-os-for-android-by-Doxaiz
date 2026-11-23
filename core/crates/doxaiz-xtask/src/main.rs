//! DoxaizOS xtask — единая точка входа для инструментария репозитория.
//!
//! Зависимостей нет (только `doxaiz-perf`), поэтому инструментарий собирается
//! и работает там, где нет crates.io, — в CI, на build-сервере LineageOS, на
//! машине сборщика.
//!
//! Подкоманды:
//!   verify                 — проверить целостность репозитория (обязательные
//!                            файлы, ключевые маркеры в них);
//!   gen-prop --ram-mb N    — напечатать low-RAM build.prop для N МиБ ОЗУ.
//!
//! Пример: `cargo run -p doxaiz-xtask -- verify`

use std::fs;
use std::path::{Path, PathBuf};
use std::process::ExitCode;

/// Корень репозитория: <root>/core/crates/doxaiz-xtask -> подняться на 3 уровня.
fn repo_root() -> PathBuf {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    manifest_dir
        .ancestors()
        .nth(3)
        .map(Path::to_path_buf)
        .unwrap_or_else(|| PathBuf::from("."))
}

/// Пара «файл → подстрока, которая обязана в нём встретиться».
/// Так мы ловим и отсутствующий файл, и файл-пустышку после неудачного merge.
const REQUIRED: &[(&str, &str)] = &[
    ("README.md", "DoxaizOS"),
    ("LICENSE", "MIT"),
    ("docs/RESEARCH.md", "Afflictio"),
    ("docs/ARCHITECTURE.md", "Launcher"),
    ("docs/BUILD.md", "repo init"),
    ("docs/PERFORMANCE.md", "zram"),
    ("docs/SECURITY.md", "SELinux"),
    ("docs/ROADMAP.md", "Cuttlefish"),
    ("docs/LAUNCHER.md", "com.doxaiz.launcher"),
    ("docs/DEVICES.md", "LineageOS"),
    ("CHANGELOG.md", "DoxaizOS"),
    ("manifest/doxaiz.xml", "<manifest"),
    (
        "overlay/vendor/doxaiz/products/doxaiz_base.mk",
        "DoxaizLauncher",
    ),
    (
        "overlay/vendor/doxaiz/products/doxaiz_base.mk",
        "ro.config.low_ram=true",
    ),
    (
        "overlay/vendor/doxaiz/apps/DoxaizLauncher/Android.mk",
        "BUILD_PREBUILT",
    ),
    (
        "overlay/vendor/doxaiz/etc/privapp-permissions-doxaiz.xml",
        "<config>",
    ),
    ("scripts/apply-overlay.sh", "vendor/doxaiz"),
    ("scripts/fetch-launcher-apk.sh", "com.doxaiz.launcher"),
    ("scripts/preflight.sh", "AOSP"),
    ("core/crates/doxaiz-metrics/src/lib.rs", "MemAvailable"),
    ("core/crates/doxaiz-metrics/src/main.rs", "doxaiz-check"),
];

fn cmd_verify() -> ExitCode {
    let root = repo_root();
    let mut failures = 0u32;
    let mut checks = 0u32;

    for (rel, needle) in REQUIRED {
        checks += 1;
        let path = root.join(rel);
        match fs::read_to_string(&path) {
            Ok(content) => {
                if content.contains(needle) {
                    println!("ok   {rel}  (находится «{needle}»)");
                } else {
                    eprintln!("FAIL {rel}  (нет маркера «{needle}»)");
                    failures += 1;
                }
            }
            Err(err) => {
                eprintln!("FAIL {rel}  (не прочитать: {err})");
                failures += 1;
            }
        }
    }

    // Отдельные негативные проверки: в ОС не должен приехать keystore или APK.
    for forbidden in [
        "overlay/vendor/doxaiz/apps/DoxaizLauncher/DoxaizLauncher.apk",
        "doxaiz.keystore",
        "platform.keystore",
    ] {
        checks += 1;
        let path = root.join(forbidden);
        if path.exists() {
            eprintln!("FAIL {forbidden}  (не должен коммититься — см. .gitignore)");
            failures += 1;
        } else {
            println!("ok   {forbidden}  (отсутствует, как и должно быть)");
        }
    }

    println!();
    println!("проверено: {checks}, ошибок: {failures}");
    if failures == 0 {
        ExitCode::SUCCESS
    } else {
        ExitCode::FAILURE
    }
}

fn cmd_gen_prop(args: &[String]) -> ExitCode {
    let mut ram_mb: Option<u64> = None;
    let mut i = 0;
    while i < args.len() {
        if args[i] == "--ram-mb" {
            i += 1;
            match args.get(i).and_then(|v| v.parse::<u64>().ok()) {
                Some(v) if v > 0 => ram_mb = Some(v),
                _ => {
                    eprintln!("ошибка: после --ram-mb нужно положительное число МиБ");
                    return ExitCode::FAILURE;
                }
            }
        } else {
            eprintln!("ошибка: неизвестный аргумент «{}»", args[i]);
            return ExitCode::FAILURE;
        }
        i += 1;
    }

    match ram_mb {
        Some(ram_mb) => {
            print!("{}", doxaiz_perf::profile_for(ram_mb).to_build_prop());
            ExitCode::SUCCESS
        }
        None => {
            eprintln!("использование: doxaiz-xtask gen-prop --ram-mb <МиБ>");
            ExitCode::FAILURE
        }
    }
}

fn usage() {
    eprintln!("DoxaizOS xtask");
    eprintln!("  verify                  проверить целостность репозитория");
    eprintln!("  gen-prop --ram-mb N     напечатать low-RAM build.prop");
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let Some(cmd) = args.first() else {
        usage();
        return ExitCode::FAILURE;
    };
    match cmd.as_str() {
        "verify" => cmd_verify(),
        "gen-prop" => cmd_gen_prop(&args[1..]),
        "-h" | "--help" | "help" => {
            usage();
            ExitCode::SUCCESS
        }
        other => {
            eprintln!("неизвестная подкоманда «{other}»");
            usage();
            ExitCode::FAILURE
        }
    }
}
