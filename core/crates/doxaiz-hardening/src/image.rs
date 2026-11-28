//! Narrow raw-ext4 data-only experiment. NOT a general image editor or signer.
//! No mounts, root, device paths, image executables, inode or xattr modification.
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Seek, SeekFrom, Write};
use std::path::Path;
use std::process::{Command, Stdio};

use crate::{ORIGINAL_RC, ORIGINAL_SCRIPT, REPLACEMENT_RC, REPLACEMENT_SCRIPT};

const INPUT_SHA: &str = "74d8cc04bd140e173ad5e94e4216bb8769939b4290cd76727f3f877ccf05df08";
const FILES: [(&str, &[u8], &str); 2] = [
    ("/system/etc/init/phh-remotectl.rc", ORIGINAL_RC, REPLACEMENT_RC),
    ("/system/bin/phh-remotectl.sh", ORIGINAL_SCRIPT, REPLACEMENT_SCRIPT),
];

fn command(program: &str, args: &[&str]) -> Result<String, String> {
    let result = Command::new("timeout").arg("120s").arg(program).args(args)
        .env("LC_ALL", "C").output().map_err(|e| e.to_string())?;
    if !result.status.success() || result.stdout.len() > 1024 * 1024 || result.stderr.len() > 1024 * 1024 {
        return Err(format!("{program} failed or output too large: {:?}", result.status.code()));
    }
    String::from_utf8(result.stdout).map_err(|e| e.to_string())
}

fn sha(path: &str) -> Result<String, String> {
    let value = command("sha256sum", &["--", path])?;
    let hash = value.split_whitespace().next().ok_or("missing SHA-256")?;
    if hash.len() != 64 || !hash.bytes().all(|b| b.is_ascii_hexdigit()) {
        return Err("invalid SHA-256 output".into());
    }
    Ok(hash.to_owned())
}

fn value_after<'a>(text: &'a str, key: &str) -> Result<&'a str, String> {
    text.split_once(key).and_then(|(_, tail)| tail.split_whitespace().next())
        .ok_or_else(|| format!("missing stat field: {key}"))
}

/// Only a single unshared extent holding one small regular file is supported.
/// Any format/flags/layout change fails closed instead of guessing a block.
fn location(stat: &str, size: usize) -> Result<u64, String> {
    if value_after(stat, "Type:")? != "regular"
        || value_after(stat, "Flags:")? != "0x80000"
        || value_after(stat, "Links:")? != "1"
        || value_after(stat, "Size:")?.parse::<usize>().map_err(|e| e.to_string())? != size {
        return Err("unsupported inode type/flags/links/size".into());
    }
    let extents = stat.split_once("EXTENTS:\n").ok_or("missing extent map")?.1.trim();
    let physical = extents.strip_prefix("(0):").ok_or("not a single first extent")?;
    if physical.is_empty() || !physical.bytes().all(|b| b.is_ascii_digit()) {
        return Err("multi-block/shared/unrecognized extent map refused".into());
    }
    let block = physical.parse::<u64>().map_err(|e| e.to_string())?;
    if block == 0 { return Err("zero block refused".into()); }
    block.checked_mul(4096).ok_or_else(|| "block offset overflow".into())
}

fn read_at(file: &mut File, offset: u64, size: usize) -> Result<Vec<u8>, String> {
    file.seek(SeekFrom::Start(offset)).map_err(|e| e.to_string())?;
    let mut bytes = vec![0; size];
    file.read_exact(&mut bytes).map_err(|e| e.to_string())?;
    Ok(bytes)
}

/// Output is deliberately an UNBOOTED experiment, never a flash/release bundle.
/// Parent/inputs must belong to this operator. Local race attacks are out of scope.
pub fn experiment(input: &Path, output: &Path) -> Result<(), String> {
    for path in input.ancestors().chain(output.parent().unwrap_or(Path::new(".")).ancestors()) {
        if !path.as_os_str().is_empty() && fs::symlink_metadata(path).map_err(|e| e.to_string())?.file_type().is_symlink() {
            return Err("symlink path refused".into());
        }
    }
    let meta = fs::symlink_metadata(input).map_err(|e| e.to_string())?;
    if !meta.is_file() || meta.len() != 1815896064 { return Err("only pinned regular raw image accepted".into()); }
    if output.exists() || fs::symlink_metadata(output).is_ok() { return Err("new output directory required".into()); }
    let input_str = input.to_str().ok_or("UTF-8 input path required")?;
    if sha(input_str)? != INPUT_SHA { return Err("raw image differs from reviewed candidate".into()); }
    let mut original = File::open(input).map_err(|e| e.to_string())?;
    if read_at(&mut original, 1080, 2)? != [0x53, 0xef]
        || read_at(&mut original, 1048, 4)? != [2, 0, 0, 0] {
        return Err("only 4096-byte-block ext4 accepted".into());
    }
    let ro_features = read_at(&mut original, 1124, 4)?;
    let ro_features = u32::from_le_bytes(ro_features.try_into().map_err(|_| "invalid feature word")?);
    if ro_features & 0x4000 != 0 {
        return Err("shared_blocks filesystem refused: cannot prove exclusive file data ownership".into());
    }
    command("e2fsck", &["-f", "-n", input_str])?;
    let mut mappings = Vec::new();
    for (path, reviewed, replacement) in FILES {
        if reviewed.len() > 4096 || replacement.len() > reviewed.len() {
            return Err("replacement must fit original small file".into());
        }
        let stat = command("debugfs", &["-R", &format!("stat {path}"), input_str])?;
        let offset = location(&stat, reviewed.len())?;
        if offset.checked_add(4096).filter(|end| *end <= meta.len()).is_none()
            || read_at(&mut original, offset, reviewed.len())? != reviewed {
            return Err("mapped data does not match reviewed bytes".into());
        }
        let mut padded = vec![b' '; reviewed.len()];
        padded[..replacement.len()].copy_from_slice(replacement.as_bytes());
        // Keep a final newline; shell exits before padding, rc has comments only.
        *padded.last_mut().ok_or("empty reviewed file")? = b'\n';
        mappings.push((path, offset, padded, stat));
    }
    if mappings[0].1 == mappings[1].1 { return Err("shared data block refused".into()); }
    fs::create_dir(output).map_err(|e| e.to_string())?;
    let raw = output.join("UNBOOTED-NOT-FOR-FLASH.img");
    let mut copy = OpenOptions::new().create_new(true).read(true).write(true).open(&raw).map_err(|e| e.to_string())?;
    original.seek(SeekFrom::Start(0)).map_err(|e| e.to_string())?;
    if std::io::copy(&mut original, &mut copy).map_err(|e| e.to_string())? != meta.len() {
        return Err("short image copy".into());
    }
    for (_, offset, data, _) in &mappings {
        copy.seek(SeekFrom::Start(*offset)).map_err(|e| e.to_string())?;
        copy.write_all(data).map_err(|e| e.to_string())?;
    }
    copy.sync_all().map_err(|e| e.to_string())?;
    let raw_str = raw.to_str().ok_or("UTF-8 output path required")?;
    for (path, offset, data, old_stat) in &mappings {
        let after = command("debugfs", &["-R", &format!("stat {path}"), raw_str])?;
        if &after != old_stat || read_at(&mut copy, *offset, data.len())? != *data {
            return Err("inode or readback differs unexpectedly".into());
        }
        let content = command("debugfs", &["-R", &format!("cat {path}"), raw_str])?;
        if content.as_bytes() != data.as_slice() { return Err("filesystem readback mismatch".into()); }
    }
    let fsck = command("e2fsck", &["-f", "-n", raw_str])?;
    // Byte-for-byte prove that no inode, xattr, directory or other data changed.
    original.seek(SeekFrom::Start(0)).map_err(|e| e.to_string())?;
    copy.seek(SeekFrom::Start(0)).map_err(|e| e.to_string())?;
    let mut left = [0u8; 65536];
    let mut right = [0u8; 65536];
    let mut position = 0u64;
    let mut changed = 0u64;
    while position < meta.len() {
        let count = (meta.len() - position).min(left.len() as u64) as usize;
        original.read_exact(&mut left[..count]).map_err(|e| e.to_string())?;
        copy.read_exact(&mut right[..count]).map_err(|e| e.to_string())?;
        if left[..count] != right[..count] {
            for index in 0..count {
                if left[index] != right[index] {
                    let absolute = position + index as u64;
                    if !mappings.iter().any(|(_, offset, data, _)| absolute >= *offset && absolute < *offset + data.len() as u64) {
                        return Err("unexpected byte change outside reviewed file ranges".into());
                    }
                    changed += 1;
                }
            }
        }
        position += count as u64;
    }
    if changed == 0 || copy.metadata().map_err(|e| e.to_string())?.len() != meta.len() {
        return Err("empty edit or image size change".into());
    }
    if sha(input_str)? != INPUT_SHA { return Err("original changed during experiment".into()); }
    let hash = sha(raw_str)?;
    if hash == INPUT_SHA { return Err("expected modified image hash".into()); }
    // Completion marker last. Original metadata/data outside two byte ranges
    // are not intentionally changed; ext4 data checksums/AVB are NOT repaired.
    let report = format!("scope=unbooted-two-file-data-only-experiment\ninput_sha256={INPUT_SHA}\noutput_sha256={hash}\ne2fsck_exit=0\ninode_stat_unchanged=true\noutside_two_file_ranges_unchanged=true\nchanged_bytes={changed}\nboot_tested=false\navb_verified=false\nrelease_approved=false\n{fsck}");
    fs::write(output.join("result.txt"), report).map_err(|e| e.to_string())?;
    Ok(())
}

/// Read-only unshare allocation simulation on the one reviewed raw image.
/// A completed diagnostic may report infeasible; it is NOT normalization.
pub fn unshare_feasibility(input: &Path, output: &Path) -> Result<(), String> {
    for path in input.ancestors().chain(output.parent().unwrap_or(Path::new(".")).ancestors()) {
        if !path.as_os_str().is_empty() && fs::symlink_metadata(path).map_err(|e| e.to_string())?.file_type().is_symlink() {
            return Err("symlink path refused".into());
        }
    }
    if !fs::symlink_metadata(input).map_err(|e| e.to_string())?.is_file()
        || fs::metadata(input).map_err(|e| e.to_string())?.len() != 1815896064 {
        return Err("only reviewed regular raw image accepted".into());
    }
    if fs::symlink_metadata(output).is_ok() { return Err("new report directory required".into()); }
    let name = input.to_str().ok_or("UTF-8 input path required")?;
    if sha(name)? != INPUT_SHA { return Err("raw image SHA mismatch".into()); }
    let mut source = File::open(input).map_err(|e| e.to_string())?;
    if read_at(&mut source, 1080, 2)? != [0x53, 0xef] { return Err("ext4 required".into()); }
    let flags = read_at(&mut source, 1124, 4)?;
    let flags = u32::from_le_bytes(flags.try_into().map_err(|_| "invalid feature word")?);
    if flags & 0x4000 == 0 { return Err("reviewed shared_blocks layout expected".into()); }
    // -n opens the FS read-only and simulates allocation. No -y/-p, mount,
    // resize, feature-bit override or image mutation is available in this mode.
    let mut child = Command::new("timeout").args(probe_args(name))
        .env("LC_ALL", "C").stdout(Stdio::piped()).stderr(Stdio::piped())
        .spawn().map_err(|e| e.to_string())?;
    let stdout = child.stdout.take().ok_or("stdout pipe missing")?;
    let stderr = child.stderr.take().ok_or("stderr pipe missing")?;
    // Drain BOTH streams concurrently with bounded memory; e2fsck may emit
    // megabytes of repeated allocation prompts even with read-only -n.
    let out = std::thread::spawn(move || drain_excerpt(stdout));
    let err = std::thread::spawn(move || drain_excerpt(stderr));
    let status = child.wait().map_err(|e| e.to_string())?;
    let (stdout, stdout_bytes, stdout_truncated) = out.join().map_err(|_| "stdout reader panicked")??;
    let (stderr, stderr_bytes, stderr_truncated) = err.join().map_err(|_| "stderr reader panicked")??;
    if sha(name)? != INPUT_SHA { return Err("input changed during read-only diagnostic".into()); }
    let code = status.code().ok_or("e2fsck supervisor terminated by signal")?;
    let completed = matches!(code, 0 | 1 | 2 | 4);
    fs::create_dir(output).map_err(|e| e.to_string())?;
    write_probe_file(&output.join("e2fsck.stdout.txt"), &stdout)?;
    write_probe_file(&output.join("e2fsck.stderr.txt"), &stderr)?;
    let conclusion = if code == 0 { "dry-run-exit-zero-not-actual-unshare" } else { "nonzero-inconclusive-or-infeasible-see-diagnostics" };
    let report = format!("scope=read-only-unshare-feasibility\ninput_sha256={INPUT_SHA}\ninput_unchanged=true\nsupervisor_exit={code}\ndiagnostic_completed={completed}\nstdout_bytes={stdout_bytes}\nstdout_excerpt={stdout_truncated}\nstderr_bytes={stderr_bytes}\nstderr_excerpt={stderr_truncated}\nassessment={conclusion}\nimage_modified=false\nnormalized_image_created=false\nboot_tested=false\nrelease_approved=false\n");
    write_probe_file(&output.join("result.txt"), report.as_bytes())
}

fn drain_excerpt(mut source: impl Read) -> Result<(Vec<u8>, u64, bool), String> {
    const HALF: usize = 16384;
    let mut head = Vec::with_capacity(HALF);
    let mut tail = Vec::with_capacity(HALF);
    let mut buffer = [0u8; 8192];
    let mut total = 0u64;
    loop {
        let count = source.read(&mut buffer).map_err(|e| e.to_string())?;
        if count == 0 { break; }
        total = total.saturating_add(count as u64);
        let prefix = (HALF - head.len()).min(count);
        head.extend_from_slice(&buffer[..prefix]);
        let remainder = &buffer[prefix..count];
        if tail.len() + remainder.len() > HALF {
            let excess = tail.len() + remainder.len() - HALF;
            tail.drain(..excess);
        }
        tail.extend_from_slice(remainder);
    }
    let truncated = total > (2 * HALF) as u64;
    if truncated { head.extend_from_slice(b"\n[TRUNCATED MIDDLE: bounded diagnostic excerpt]\n"); }
    head.extend_from_slice(&tail);
    Ok((head, total, truncated))
}

fn probe_args(name: &str) -> [&str; 6] {
    ["120s", "e2fsck", "-n", "-E", "unshare_blocks", name]
}

fn write_probe_file(path: &Path, bytes: &[u8]) -> Result<(), String> {
    let mut file = OpenOptions::new().create_new(true).write(true).open(path).map_err(|e| e.to_string())?;
    file.write_all(bytes).map_err(|e| e.to_string())?;
    file.sync_all().map_err(|e| e.to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn diagnostic_capture_keeps_bounded_head_and_tail() {
        let mut bytes = vec![b'x'; 100000];
        bytes[..5].copy_from_slice(b"start");
        bytes[99997..].copy_from_slice(b"end");
        let (excerpt, count, truncated) = drain_excerpt(std::io::Cursor::new(bytes)).unwrap();
        assert_eq!(count, 100000);
        assert!(truncated);
        assert!(excerpt.len() < 33000);
        assert!(excerpt.starts_with(b"start"));
        assert!(excerpt.ends_with(b"end"));
        for bytes in [Vec::new(), b"short log".to_vec(), vec![b'y'; 32768]] {
            let (excerpt, count, truncated) = drain_excerpt(std::io::Cursor::new(&bytes)).unwrap();
            assert!(!truncated);
            assert_eq!(count, bytes.len() as u64);
            assert_eq!(excerpt, bytes);
        }
    }

    #[test]
    fn feasibility_command_is_read_only_and_has_no_repair_flags() {
        let args = probe_args("/owned/regular-file.img");
        assert_eq!(args, ["120s", "e2fsck", "-n", "-E", "unshare_blocks", "/owned/regular-file.img"]);
        assert!(!args.contains(&"-y"));
        assert!(!args.contains(&"-p"));
    }

    #[test]
    fn mapping_is_narrow_and_fail_closed() {
        let stat = "Inode: 42 Type: regular Mode: 0644 Flags: 0x80000\nSize: 123\nLinks: 1\nEXTENTS:\n(0):99\n";
        assert_eq!(location(stat, 123).unwrap(), 99 * 4096);
        for bad in [stat.replace("0x80000", "0x180000"), stat.replace("Links: 1", "Links: 2"),
                    stat.replace("regular", "symlink"), stat.replace("(0):99", "(0-1):99-100"),
                    stat.replace("(0):99", "(0):0"), stat.replace("Size: 123", "Size: 124")] {
            assert!(location(&bad, 123).is_err());
        }
    }
}
