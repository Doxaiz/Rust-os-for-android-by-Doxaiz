# Reviewed upstream input, never execute

These `.original` files are byte-exact policy inputs extracted from the ready
Andy Yan GSI, not runnable DoxaizOS programs. Their original provenance and
contents are recorded in `docs/evidence/ready-security-46169653206.json` at the
repository root. Upstream matching source:
https://github.com/TrebleDroid/device_phh_treble/tree/94a405915c38e8c09fc01505a56c76c927fb45bf/remote

They retain their upstream provenance; the crate's MIT license declaration is
not an assertion that third-party Android source/images are relicensed under
MIT. Full upstream distribution/licensing review remains required before a
modified firmware is redistributed. Nothing here authenticates the publisher.

The Rust tool compares input bytes against these reviewed files. A changed
upstream file is refused and requires renewed review, not a forced override.
