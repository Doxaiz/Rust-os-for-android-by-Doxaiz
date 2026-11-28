//! Explicitly experimental host tool, never a phone flashing command.
#![forbid(unsafe_code)]
use std::{path::Path, process::ExitCode};
fn main() -> ExitCode {
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    if args.len() != 3 || args[0] != "--allow-unbooted-experiment" {
        eprintln!("Usage: doxaiz-experiment-image --allow-unbooted-experiment PINNED_RAW_IMAGE NEW_OUTPUT_DIRECTORY");
        return ExitCode::from(2);
    }
    match doxaiz_hardening::image::experiment(Path::new(&args[1]), Path::new(&args[2])) {
        Ok(()) => {
            println!("Static two-file image experiment completed. NOT booted, NOT AVB verified, NOT FOR FLASHING.");
            ExitCode::SUCCESS
        }
        Err(error) => {
            eprintln!("Experiment refused/failed: {error}. Any partial output is invalid; do not use it.");
            ExitCode::FAILURE
        }
    }
}
