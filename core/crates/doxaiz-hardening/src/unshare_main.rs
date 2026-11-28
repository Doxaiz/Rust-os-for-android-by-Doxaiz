//! Read-only host diagnostic; exit 0 means the diagnostic was recorded, not
//! that the filesystem was normalized or an image is safe to flash.
#![forbid(unsafe_code)]
use std::{path::Path, process::ExitCode};
fn main() -> ExitCode {
    let args: Vec<_> = std::env::args_os().skip(1).collect();
    if args.len() != 2 {
        eprintln!("Usage: doxaiz-unshare-probe PINNED_RAW_IMAGE NEW_REPORT_DIRECTORY");
        return ExitCode::from(2);
    }
    match doxaiz_hardening::image::unshare_feasibility(Path::new(&args[0]), Path::new(&args[1])) {
        Ok(()) => {
            println!("Read-only unshare diagnostic recorded. Read supervisor_exit, diagnostic_completed and diagnostics. NO image modified, NO boot acceptance.");
            ExitCode::SUCCESS
        }
        Err(error) => {
            eprintln!("Diagnostic refused/failed: {error}");
            if std::env::var("GITHUB_ACTIONS").as_deref() == Ok("true") {
                let message = error.replace('%', "%25").replace('\r', "%0D").replace('\n', "%0A");
                eprintln!("::error title=Rust unshare diagnostic refused::{message}");
            }
            ExitCode::FAILURE
        }
    }
}
