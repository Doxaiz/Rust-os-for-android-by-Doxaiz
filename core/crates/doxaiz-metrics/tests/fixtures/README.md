# Memory parser fixtures

These are **synthetic, source-derived format examples**, not captured device output,
not Doxaiz Launcher measurements, and not verbatim AOSP dumps. Values and package
names are invented; the separate RSS row deliberately exercises a negative case.

Inspected through GitHub API on 2026-11-23:

* [Android 15 ActivityThread.java](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-15.0.0_r1/core/java/android/app/ActivityThread.java), blob `b384326201fcf36ece78f70d549a22b9e0d5fa04`.
* [Android 16 ActivityThread.java](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-16.0.0_r1/core/java/android/app/ActivityThread.java), blob `4987624be71997c03c4061b9e1eaff1998559c7f`.

`dumpMemInfoTable` prints the HEAP_COLUMN/HEAP_FULL_COLUMN row named `TOTAL`
(without a colon), followed by an App Summary whose labels include `TOTAL PSS:`,
`TOTAL RSS:` and `TOTAL SWAP PSS:` (or `TOTAL SWAP (KB):`). The parser must extract
PSS, not RSS or swap. Summary PSS takes precedence if both formats are present.

Run with `cd core && cargo test -p doxaiz-metrics`.
