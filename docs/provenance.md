# Migration provenance

The standalone public repository starts with a clean source import from legacy local commit **`ba75cb436ac70f00043d95266929d25708ee0085`**, the committed fast5 snapshot dated 2026-10-02. Original history, installation evidence and recovery packages remain in the separate device project/local checkout. No legacy Git history was copied into this repository.

[import.json](../provenance/import.json) records the allowlisted original paths, new paths and SHA-256 fingerprints of all 50 imported files. These are **historical import fingerprints**, not a restriction on future development. Initial migration validation compares every imported file except the intentionally rewritten README, `.gitignore`, NOTICES and one renderer-test portability correction. Firmware code, patch, existing tools and remaining tests, packaged presets and optional theme text remain byte-identical.

The new wrapper commands, toolchain input lock, GitHub workflow and standalone documentation were added on 2026-10-05. No native algorithm, settings layout, plugin ABI, codec API or package theme payload change is part of the migration.

The six toolchain archive fingerprints were recovered from the retained successful build downloads and independently rechecked by the cold bootstrap against fresh HTTPS downloads from GNU/GCC servers. The original upstream source fingerprint and official 4.0 package fingerprint are preserved.

AI-generation and third-party attribution remains in [NOTICES](../NOTICES.md). Successful host checks do not imply hardware validation, independent human code review or upstream acceptance.

The imported renderer fixture originally relied on an unsigned negation converted back to a signed level. GCC 13 rejects the mixed-sign conditional under `-Werror`. The migration explicitly casts the bounded remainder to `int` before negation; generated test levels and firmware rendering are unchanged. This is the only imported test adjustment.
