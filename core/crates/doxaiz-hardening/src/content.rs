//! Inode-based regular-file comparison, not a complete filesystem audit.
//! Numeric dump destinations only: no image pathname becomes a host path.
use std::{collections::BTreeMap, fs::{self, File, OpenOptions}, io::{Read, Seek, SeekFrom, Write}, path::Path};

fn at(file: &mut File, offset: u64, len: usize) -> Result<Vec<u8>, String> {
    file.seek(SeekFrom::Start(offset)).map_err(|e| e.to_string())?;
    let mut data = vec![0; len];
    file.read_exact(&mut data).map_err(|e| e.to_string())?;
    Ok(data)
}
fn word(data: &[u8], index: usize) -> u32 {
    u32::from_le_bytes(data[index..index+4].try_into().unwrap())
}
fn short(data: &[u8], index: usize) -> u16 {
    u16::from_le_bytes(data[index..index+2].try_into().unwrap())
}
fn regular_inodes(image: &Path) -> Result<BTreeMap<u32, u64>, String> {
    let mut file = File::open(image).map_err(|e| e.to_string())?;
    let sb = at(&mut file, 1024, 1024)?;
    if short(&sb, 56) != 0xef53 || word(&sb, 24) != 2 { return Err("4096-byte ext4 required".into()); }
    let inodes = word(&sb, 0);
    let per_group = word(&sb, 40);
    let inode_size = short(&sb, 88) as u64;
    let incompatible = word(&sb, 96);
    // meta_bg changes descriptor placement; inline/encrypted data are not
    // supported by this audit. Fail rather than silently omit files.
    if incompatible & (0x10 | 0x8000 | 0x10000) != 0 { return Err("unsupported ext4 layout/data feature".into()); }
    if inodes == 0 || inodes > 100000 || per_group == 0 || inode_size < 128 || inode_size > 4096 {
        return Err("unsupported inode geometry".into());
    }
    let desc_size = if incompatible & 0x80 != 0 { short(&sb, 254) as u64 } else { 32 };
    if ![32, 64].contains(&desc_size) { return Err("unsupported descriptor size".into()); }
    let mut result = BTreeMap::new();
    for group in 0..inodes.div_ceil(per_group) {
        let desc = at(&mut file, 4096 + group as u64 * desc_size, desc_size as usize)?;
        if short(&desc, 18) & 1 != 0 { continue; } // INODE_UNINIT: no allocated inodes
        let high = |offset| if desc_size == 64 { (word(&desc, offset) as u64) << 32 } else { 0 };
        let bitmap_block = word(&desc, 4) as u64 | high(36);
        let table_block = word(&desc, 8) as u64 | high(40);
        if per_group > 32768 || bitmap_block == 0 || table_block == 0 { return Err("invalid inode descriptor".into()); }
        let bitmap = at(&mut file, bitmap_block * 4096, 4096)?;
        for local in 0..per_group.min(inodes - group * per_group) {
            if bitmap[local as usize / 8] & (1 << (local % 8)) == 0 { continue; }
            let inode = at(&mut file, table_block * 4096 + local as u64 * inode_size, inode_size as usize)?;
            let mode = short(&inode, 0);
            if mode & 0xf000 != 0x8000 { continue; }
            let number = group * per_group + local + 1;
            // Reserved resize inode holds filesystem layout metadata, not a
            // user regular file. It changes when the filesystem grows.
            if number < 11 { continue; }
            let size = word(&inode, 4) as u64 | ((word(&inode, 108) as u64) << 32);
            if size > 1024 * 1024 * 1024 { return Err("regular file exceeds audit bound".into()); }
            result.insert(number, size);
        }
    }
    if result.is_empty() { return Err("no regular files found".into()); }
    let bytes: u64 = result.values().sum();
    if result.len() > 10000 || bytes > 4 * 1024 * 1024 * 1024 {
        return Err("regular content audit exceeds file/disk bound".into());
    }
    Ok(result)
}

fn equal_streams(mut a: impl Read, mut b: impl Read) -> Result<bool, String> {
    let mut left = [0u8; 65536];
    let mut right = [0u8; 65536];
    loop {
        // fill each chunk to handle short reads independently.
        let fill = |source: &mut dyn Read, buffer: &mut [u8]| -> Result<usize, String> {
            let mut count = 0;
            while count < buffer.len() {
                let n = source.read(&mut buffer[count..]).map_err(|e| e.to_string())?;
                if n == 0 { break; }
                count += n;
            }
            Ok(count)
        };
        let x = fill(&mut a, &mut left)?;
        let y = fill(&mut b, &mut right)?;
        if x != y || left[..x] != right[..y] { return Ok(false); }
        if x == 0 { return Ok(true); }
    }
}

pub(crate) fn compare(before: &Path, after: &Path, root: &Path) -> Result<String, String> {
    let baseline = regular_inodes(before)?;
    if baseline != regular_inodes(after)? { return Err("allocated regular inode identities/sizes changed".into()); }
    let dump_root = root.join("content-dumps");
    fs::create_dir(&dump_root).map_err(|e| e.to_string())?;
    let result = (|| {
        for (label, image) in [("before", before), ("after", after)] {
            let dir = dump_root.join(label);
            fs::create_dir(&dir).map_err(|e| e.to_string())?;
            let script = root.join(format!("dump-{label}.commands"));
            let mut commands = OpenOptions::new().create_new(true).write(true).open(&script).map_err(|e| e.to_string())?;
            // Paths controlled by this operator, not image directory entries.
            for path in [&dir, &script, image] {
                let text = path.to_str().ok_or("UTF-8 host path required")?;
                if !text.bytes().all(|c| c.is_ascii_alphanumeric() || b"/._-".contains(&c)) {
                    return Err("debugfs host path requires plain safe characters".into());
                }
            }
            for inode in baseline.keys() {
                writeln!(commands, "dump <{inode}> {}/{inode}", dir.display()).map_err(|e| e.to_string())?;
            }
            commands.sync_all().map_err(|e| e.to_string())?;
            super::image::normalization_stage(root, &format!("dump-{label}"), "debugfs", &["-f", script.to_str().unwrap(), image.to_str().unwrap()])?;
        }
        let mut bytes = 0u64;
        for (inode, size) in &baseline {
            let paths = [dump_root.join(format!("before/{inode}")), dump_root.join(format!("after/{inode}"))];
            for path in &paths {
                let meta = fs::symlink_metadata(path).map_err(|e| e.to_string())?;
                if !meta.is_file() || meta.len() != *size { return Err(format!("missing/incomplete numeric dump for inode {inode}")); }
            }
            if !equal_streams(File::open(&paths[0]).map_err(|e| e.to_string())?, File::open(&paths[1]).map_err(|e| e.to_string())?)? {
                return Err(format!("regular file content differs: inode {inode}"));
            }
            bytes += size;
        }
        Ok(format!("regular_files_compared={}\nlogical_bytes_compared={bytes}\nregular_file_bytes_equal=true\nreserved_inodes_excluded=1-10\ndirectories_symlinks_special_files_verified=false\nall_metadata_xattrs_verified=false\n", baseline.len()))
    })();
    fs::remove_dir_all(&dump_root).map_err(|e| e.to_string())?;
    result
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn streaming_comparison_detects_length_and_late_byte_changes() {
        let data = vec![13u8; 150000];
        assert!(equal_streams(&data[..], &data[..]).unwrap());
        assert!(!equal_streams(&data[..], &data[..149999]).unwrap());
        let mut changed = data.clone(); changed[149999] = 14;
        assert!(!equal_streams(&data[..], &changed[..]).unwrap());
        assert!(equal_streams(&b""[..], &b""[..]).unwrap());
    }
    #[test]
    fn endian_fields_are_explicit() {
        assert_eq!(short(&[1,2,3,4], 0), 513);
        assert_eq!(word(&[1,2,3,4], 0), 67305985);
    }
    #[test]
    fn synthetic_inode_bitmap_selects_only_allocated_nonreserved_regular_files() {
        use std::sync::atomic::{AtomicU64, Ordering};
        static COUNTER: AtomicU64 = AtomicU64::new(0);
        let path = std::env::temp_dir().join(format!("doxaiz-inode-test-{}-{}", std::process::id(), COUNTER.fetch_add(1, Ordering::Relaxed)));
        let mut bytes = vec![0u8; 5 * 4096];
        bytes[1024..1028].copy_from_slice(&32u32.to_le_bytes());
        bytes[1048..1052].copy_from_slice(&2u32.to_le_bytes());
        bytes[1064..1068].copy_from_slice(&32u32.to_le_bytes());
        bytes[1080..1082].copy_from_slice(&0xef53u16.to_le_bytes());
        bytes[1112..1114].copy_from_slice(&128u16.to_le_bytes());
        bytes[4100..4104].copy_from_slice(&2u32.to_le_bytes()); // inode bitmap
        bytes[4104..4108].copy_from_slice(&3u32.to_le_bytes()); // inode table
        // Reserved regular inode 7, allocated regular 11, directory 12;
        // regular inode 13 has bytes in the table but is NOT allocated.
        for (inode, mode) in [(7, 0x8000u16), (11, 0x8000), (12, 0x4000), (13, 0x8000)] {
            let offset = 3 * 4096 + (inode - 1) * 128;
            bytes[offset..offset+2].copy_from_slice(&mode.to_le_bytes());
            bytes[offset+4..offset+8].copy_from_slice(&123u32.to_le_bytes());
            if inode != 13 { bytes[2 * 4096 + (inode-1)/8] |= 1 << ((inode-1)%8); }
        }
        let mut file = OpenOptions::new().create_new(true).write(true).open(&path).unwrap();
        file.write_all(&bytes).unwrap(); drop(file);
        assert_eq!(regular_inodes(&path).unwrap(), BTreeMap::from([(11, 123)]));
        // meta_bg is not silently interpreted using the wrong descriptor map.
        bytes[1120..1124].copy_from_slice(&0x10u32.to_le_bytes());
        fs::write(&path, &bytes).unwrap();
        assert!(regular_inodes(&path).unwrap_err().contains("unsupported ext4"));
        bytes.truncate(1050);
        fs::write(&path, &bytes).unwrap();
        assert!(regular_inodes(&path).is_err());
        fs::remove_file(path).unwrap();
    }

}
