//! Host-only, fail-closed preparation of TWO remote-support replacement files.
//! Does not mount/modify an image, run image scripts, change ADB or flash a device.
#![forbid(unsafe_code)]

use std::fs::{self, File, OpenOptions};
use std::io::{Read, Write};
use std::path::Path;

const ORIGINAL_RC: &[u8] = include_bytes!("../policy/phh-remotectl.rc.original");
const ORIGINAL_SCRIPT: &[u8] = include_bytes!("../policy/phh-remotectl.sh.original");
pub const REPLACEMENT_RC: &str = "# DoxaizOS: remote-support service and TCP ADB triggers intentionally omitted.\n# No service declaration, imports or property actions in this replacement.\n";
pub const REPLACEMENT_SCRIPT: &str = "#!/system/bin/sh\n# DoxaizOS: remote-support entry point intentionally unavailable.\nexit 1\n";
const NOTICE: &str = "scope=two-file-host-patch-only\npolicy=ready-a64-20261109-remote-v1\nsource_evidence=ready-security-46169653206\nimage_modified=false\nboot_tested=false\nruntime_security_verified=false\nDo not flash these files or claim a hardened ROM. Image integration, labels, AVB, other start paths and runtime checks remain required.\n";

fn read_regular(path: &Path) -> Result<Vec<u8>, String> {
    // Reject symlinks in all existing path components, not just the leaf.
    for ancestor in path.ancestors() {
        if !ancestor.as_os_str().is_empty() {
            let meta = fs::symlink_metadata(ancestor).map_err(|e| e.to_string())?;
            if meta.file_type().is_symlink() {
                return Err("symlink input/ancestor refused".into());
            }
        }
    }
    let meta = fs::symlink_metadata(path).map_err(|e| e.to_string())?;
    if !meta.is_file() || meta.len() > 16384 {
        return Err("regular input file <= 16 KiB required".into());
    }
    let mut data = Vec::new();
    File::open(path).map_err(|e| e.to_string())?.take(16385)
        .read_to_end(&mut data).map_err(|e| e.to_string())?;
    if data.len() > 16384 {
        return Err("input grew past size limit".into());
    }
    Ok(data)
}

fn write_new(path: &Path, data: &[u8]) -> Result<(), String> {
    let mut file = OpenOptions::new().write(true).create_new(true)
        .open(path).map_err(|e| e.to_string())?;
    file.write_all(data).map_err(|e| e.to_string())?;
    file.sync_all().map_err(|e| e.to_string())
}

/// Exact byte comparison pins the reviewed contents, not merely a filename or
/// a previously observed hash. No third-party crypto implementation is added.
/// Output is a NEW directory; inputs are never edited and modes/SELinux labels
/// are NOT an Android integration contract. Local hostile filesystem races are
/// out of scope: run in an owned disposable workspace, never as root.
pub fn prepare(rc: &Path, script: &Path, output: &Path) -> Result<(), String> {
    let rc_bytes = read_regular(rc)?;
    let script_bytes = read_regular(script)?;
    if rc_bytes != ORIGINAL_RC || script_bytes != ORIGINAL_SCRIPT {
        return Err("unreviewed remote-support configuration: exact policy mismatch".into());
    }
    let parent = output.parent().filter(|p| !p.as_os_str().is_empty()).unwrap_or(Path::new("."));
    for ancestor in parent.ancestors() {
        if !ancestor.as_os_str().is_empty() && fs::symlink_metadata(ancestor)
            .map_err(|e| e.to_string())?.file_type().is_symlink() {
            return Err("symlink output ancestor refused".into());
        }
    }
    fs::create_dir(output).map_err(|e| format!("new output directory required: {e}"))?;
    // Any IO failure leaves an explicitly incomplete directory, never retries
    // over existing evidence. NOTICE is the last completion record.
    write_new(&output.join("phh-remotectl.rc"), REPLACEMENT_RC.as_bytes())?;
    write_new(&output.join("phh-remotectl.sh"), REPLACEMENT_SCRIPT.as_bytes())?;
    write_new(&output.join("NOTICE.txt"), NOTICE.as_bytes())?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicUsize, Ordering};
    static NEXT: AtomicUsize = AtomicUsize::new(0);

    fn fixture() -> std::path::PathBuf {
        let root = std::env::temp_dir().join(format!("doxaiz-hardening-{}-{}", std::process::id(), NEXT.fetch_add(1, Ordering::Relaxed)));
        fs::create_dir(&root).unwrap();
        fs::write(root.join("original.rc"), ORIGINAL_RC).unwrap();
        fs::write(root.join("original.sh"), ORIGINAL_SCRIPT).unwrap();
        root
    }

    #[test]
    fn outputs_inert_replacements_without_changing_inputs() {
        let root = fixture();
        let output = root.join("patch");
        prepare(&root.join("original.rc"), &root.join("original.sh"), &output).unwrap();
        assert_eq!(fs::read(root.join("original.rc")).unwrap(), ORIGINAL_RC);
        assert_eq!(fs::read(root.join("original.sh")).unwrap(), ORIGINAL_SCRIPT);
        assert!(REPLACEMENT_RC.lines().all(|line| line.is_empty() || line.starts_with('#')));
        assert_eq!(REPLACEMENT_SCRIPT.lines().filter(|line| !line.starts_with('#')).collect::<Vec<_>>(), ["exit 1"]);
        assert_eq!(fs::read_to_string(output.join("phh-remotectl.rc")).unwrap(), REPLACEMENT_RC);
        assert_eq!(fs::read_to_string(output.join("phh-remotectl.sh")).unwrap(), REPLACEMENT_SCRIPT);
        assert!(fs::read_to_string(output.join("NOTICE.txt")).unwrap().contains("image_modified=false"));
        assert!(prepare(&root.join("original.rc"), &root.join("original.sh"), &output).is_err());
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn drift_missing_and_oversized_files_fail_before_output_creation() {
        let oversized = vec![b'x'; 16385];
        for replacement in [b"different version".as_slice(), b"", oversized.as_slice()] {
            let root = fixture();
            fs::write(root.join("original.rc"), replacement).unwrap();
            assert!(prepare(&root.join("original.rc"), &root.join("original.sh"), &root.join("patch")).is_err());
            assert!(!root.join("patch").exists());
            fs::remove_dir_all(root).unwrap();
        }
        let root = fixture();
        fs::remove_file(root.join("original.sh")).unwrap();
        assert!(prepare(&root.join("original.rc"), &root.join("original.sh"), &root.join("patch")).is_err());
        assert!(!root.join("patch").exists());
        fs::remove_dir_all(root).unwrap();
    }

    #[cfg(unix)]
    #[test]
    fn refuses_input_and_output_symlinks() {
        use std::os::unix::fs::symlink;
        let root = fixture();
        symlink(root.join("original.rc"), root.join("link.rc")).unwrap();
        assert!(prepare(&root.join("link.rc"), &root.join("original.sh"), &root.join("patch")).is_err());
        symlink(&root, root.join("linked-parent")).unwrap();
        assert!(prepare(&root.join("original.rc"), &root.join("original.sh"), &root.join("linked-parent/patch")).is_err());
        assert!(!root.join("patch").exists());
        fs::remove_dir_all(root).unwrap();
    }
}
