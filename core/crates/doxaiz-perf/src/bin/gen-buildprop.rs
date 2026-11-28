//! Печать low-RAM build.prop-фрагмента DoxaizOS для заданного объёма ОЗУ.
//!
//! Пример: `cargo run -p doxaiz-perf --bin gen-buildprop -- --ram-mb 2048`

use std::process::ExitCode;

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let mut ram_mb: Option<u64> = None;

    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--ram-mb" => {
                i += 1;
                let Some(raw) = args.get(i) else {
                    eprintln!("ошибка: после --ram-mb нужно число, например --ram-mb 2048");
                    return ExitCode::FAILURE;
                };
                match raw.parse::<u64>() {
                    Ok(v) if v > 0 => ram_mb = Some(v),
                    _ => {
                        eprintln!("ошибка: «{raw}» — не похоже на объём ОЗУ в МиБ (> 0)");
                        return ExitCode::FAILURE;
                    }
                }
            }
            "-h" | "--help" => {
                println!("Использование: gen-buildprop --ram-mb <МиБ>  (например, --ram-mb 2048)");
                return ExitCode::SUCCESS;
            }
            other => {
                eprintln!("ошибка: неизвестный аргумент «{other}» (см. --help)");
                return ExitCode::FAILURE;
            }
        }
        i += 1;
    }

    let Some(ram_mb) = ram_mb else {
        eprintln!("ошибка: укажите --ram-mb (см. --help)");
        return ExitCode::FAILURE;
    };

    print!("{}", doxaiz_perf::profile_for(ram_mb).to_build_prop());
    ExitCode::SUCCESS
}
