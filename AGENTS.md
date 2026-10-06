# Working agreements

- This is an experimental Rockbox 4.0 patch/build project for `ipod6g`.
- Preserve pinned source inputs and fingerprint checks. Keep matching firmware, plugins and codecs together.
- Run `python3 tools/test.py --output reports/portable` for changes to native code or tooling. Build/parser/package validation is required for firmware changes.
- Document user-visible behavior changes and distinguish host tests from physical iPod observations.
- Keep upstream and theme licenses, attribution and AI-generation provenance intact.
- Do not commit music, personal settings, device records, backups, downloaded assets, compiled firmware or toolchains.
- Device-specific configuration/history/recovery lives in the separate `ipod-classic-6.5` project. CI must never access a device volume.
- Installation remains dry-run unless `--apply` is explicitly supplied. No bootloader or partition changes are part of this project.
- Whenever requesting a reply or choice, provide clear one-letter options when sufficient.
