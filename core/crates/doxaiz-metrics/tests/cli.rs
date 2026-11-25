//! End-to-end CLI exit status checks with synthetic diagnostic input.
use std::{fs, process::Command, sync::atomic::{AtomicUsize, Ordering}};

static NEXT: AtomicUsize = AtomicUsize::new(0);

fn check(mode: &str, content: &str, expected: i32) {
    let path = std::env::temp_dir().join(format!(
        "doxaiz-cli-{}-{}.txt", std::process::id(), NEXT.fetch_add(1, Ordering::Relaxed)
    ));
    fs::write(&path, content).unwrap();
    let output = Command::new(env!("CARGO_BIN_EXE_doxaiz-check"))
        .arg(mode).arg(&path).output();
    fs::remove_file(path).unwrap();
    let output = output.unwrap();
    assert_eq!(output.status.code(), Some(expected), "stdout={} stderr={}",
        String::from_utf8_lossy(&output.stdout), String::from_utf8_lossy(&output.stderr));
    assert_eq!(String::from_utf8_lossy(&output.stdout).contains("бюджет выполнен"), expected == 0);
}

#[test]
fn empty_diagnostics_are_inconclusive_not_successful() {
    for mode in ["meminfo", "coldstart", "jank", "pss"] {
        check(mode, "", 2);
    }
}

#[test]
fn valid_pss_passes_and_excessive_pss_fails() {
    check("pss", "TOTAL PSS: 46100", 0);
    check("pss", "TOTAL PSS: 131072", 1);
}

#[test]
fn missing_completion_is_inconclusive_but_failure_has_priority() {
    check("coldstart", "TotalTime: 200", 2);
    check("coldstart", "TotalTime: 900", 1);
    check("coldstart", "Status: ok\nLaunchState: COLD\nTotalTime: 200\nComplete", 0);
}

#[test]
fn source_derived_zero_frame_report_is_inconclusive() {
    check("jank", "Total frames rendered: 0\nJanky frames: 0 (0.00%)\n90th percentile: 0ms", 2);
    check("jank", "Total frames rendered: 100\nJanky frames: 1 (1.00%)\n90th percentile: 12ms", 0);
    check("jank", "Total frames rendered: 100\nJanky frames: 1 (NaN%)\n90th percentile: NaNms", 2);
}

#[test]
fn launch_status_and_state_are_required_for_coldstart_success() {
    for (prefix, code) in [
        ("Status: timeout\nLaunchState: COLD", 1),
        ("Error type 3\nStatus: ok\nLaunchState: COLD", 1),
        ("Status: ok\nLaunchState: WARM", 2),
        ("Status: ok\nLaunchState: HOT", 2),
        ("Status: ok", 2),
        ("LaunchState: COLD", 2),
        ("Warning: Activity not started, intent has been delivered to currently running top-most instance.\nStatus: ok\nLaunchState: COLD", 2),
    ] {
        check("coldstart", &format!("{prefix}\nTotalTime: 0\nComplete"), code);
    }
}
