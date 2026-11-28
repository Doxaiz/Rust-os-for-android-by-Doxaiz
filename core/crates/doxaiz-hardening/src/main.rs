//! Host CLI, never a daemon or executable installed on the phone.
#![forbid(unsafe_code)]
use std::{path::Path, process::ExitCode};

fn main() -> ExitCode {
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    if args.len() != 3 {
        eprintln!("Usage: doxaiz-harden-remote EXTRACTED_RC EXTRACTED_SCRIPT NEW_PATCH_DIRECTORY");
        return ExitCode::from(2);
    }
    match doxaiz_hardening::prepare(Path::new(&args[0]), Path::new(&args[1]), Path::new(&args[2])) {
        Ok(()) => {
            println!("Prepared two reviewed replacements ONLY. Image unchanged; NOT a boot/security acceptance PASS.");
            ExitCode::SUCCESS
        }
        Err(error) => {
            eprintln!("Refused: {error}. No image modification attempted; partial output, if any, must not be used.");
            ExitCode::FAILURE
        }
    }
}
